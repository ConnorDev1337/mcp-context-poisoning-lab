"""Page rendering and text extraction.

``render_page`` turns a scenario page into HTML, embedding the attacker payload
through the chosen vector. ``extract`` models the three ways a browsing tool can
turn that HTML back into text for the model:

* ``reader``   - visible text only, like a reader view;
* ``markdown`` - visible text plus ``alt`` / ``title`` / ``aria-label`` text and
  link targets, like an HTML-to-Markdown converter;
* ``raw``      - the HTML as served, including comments, metadata and hidden
  elements.

Which vectors survive which mode is a measured result, not an assumption; see the
source-vs-rendered survival table in the report.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

from .attacks import Markers, embed, payload_text
from .scenarios import PageSpec, Scenario

# ----------------------------------------------------------------------------
# A small, deterministic Markdown subset -> HTML
# ----------------------------------------------------------------------------

_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_BOLD = re.compile(r"\*\*([^*]+)\*\*")
_CODE = re.compile(r"`([^`]+)`")


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _inline(text: str) -> str:
    text = _esc(text)
    text = _CODE.sub(lambda m: f"<code>{m.group(1)}</code>", text)
    text = _BOLD.sub(lambda m: f"<strong>{m.group(1)}</strong>", text)
    text = _LINK.sub(lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>', text)
    return text


def md_to_html(md: str) -> str:
    """Convert a small Markdown subset (headings, paragraphs, lists, links)."""
    html: list[str] = []
    lines = md.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if not line:
            i += 1
            continue
        heading = re.match(r"(#{1,6})\s+(.*)", line)
        if heading:
            level = len(heading.group(1))
            html.append(f"<h{level}>{_inline(heading.group(2))}</h{level}>")
            i += 1
            continue
        if re.match(r"[-*]\s+", line):
            items = []
            while i < len(lines) and re.match(r"[-*]\s+", lines[i]):
                items.append(f"<li>{_inline(lines[i].split(None, 1)[1])}</li>")
                i += 1
            html.append("<ul>" + "".join(items) + "</ul>")
            continue
        para = [line]
        i += 1
        while i < len(lines) and lines[i].strip():
            para.append(lines[i].rstrip())
            i += 1
        html.append(f"<p>{_inline(' '.join(para))}</p>")
    return "\n".join(html)


# ----------------------------------------------------------------------------
# Render a scenario page
# ----------------------------------------------------------------------------


def render_page(scenario: Scenario, page: PageSpec, m: Markers) -> str:
    """Render one page to a full HTML document, embedding the payload if any."""
    head_extra = ""
    body_extra = ""
    if page.inject is not None and page.inject.vector != "tool_description":
        payload = payload_text(scenario.objective, m)
        snippet = embed(page.inject.vector, payload)
        if page.inject.vector == "meta_tag":
            head_extra = snippet
        else:
            body_extra = snippet
    badge = ""
    if page.authority:
        badge = f'<p class="badge">[{_esc(page.authority.upper())} SOURCE]</p>'
    body = md_to_html(page.body_md)
    return (
        '<!doctype html>\n<html lang="en">\n<head>\n'
        '<meta charset="utf-8">\n'
        f"<title>{_esc(page.title)}</title>\n{head_extra}\n</head>\n<body>\n"
        f"<header><h1>{_esc(page.title)}</h1>{badge}</header>\n"
        f"<main>\n{body}\n{body_extra}\n</main>\n</body>\n</html>\n"
    )


# ----------------------------------------------------------------------------
# Extraction
# ----------------------------------------------------------------------------

_SKIP_CONTENT = {"script", "style", "head", "title", "svg", "noscript"}
_HIDDEN_STYLE = re.compile(r"display\s*:\s*none|visibility\s*:\s*hidden", re.I)


class _Extractor(HTMLParser):
    """Collect text according to an extraction mode."""

    def __init__(self, mode: str) -> None:
        super().__init__(convert_charrefs=True)
        self.mode = mode
        self.parts: list[str] = []
        self._skip_depth = 0
        self._hidden_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k: (v or "") for k, v in attrs}
        if self.mode == "reader" and _HIDDEN_STYLE.search(a.get("style", "")):
            self._hidden_depth += 1
        if tag in _SKIP_CONTENT and self.mode != "raw":
            self._skip_depth += 1
        if self.mode in {"markdown", "raw"}:
            for name in ("alt", "title", "aria-label"):
                if a.get(name):
                    self.parts.append(a[name])
            if tag == "a" and a.get("href"):
                self.parts.append(a["href"])
        if self.mode == "raw":
            for name in ("content", "data-note"):
                if a.get(name):
                    self.parts.append(a[name])

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_CONTENT and self.mode != "raw":
            self._skip_depth = max(0, self._skip_depth - 1)
        if self.mode == "reader" and self._hidden_depth and tag in {"div", "p", "span"}:
            self._hidden_depth = max(0, self._hidden_depth - 1)

    def handle_data(self, data: str) -> None:
        if self._skip_depth or (self.mode == "reader" and self._hidden_depth):
            return
        if data.strip():
            self.parts.append(data.strip())

    def handle_comment(self, data: str) -> None:
        if self.mode == "raw":
            self.parts.append(data.strip())


def extract(html: str, mode: str = "reader") -> str:
    """Extract text from ``html`` in the given extraction ``mode``."""
    if mode not in {"reader", "markdown", "raw"}:
        raise ValueError(f"unknown extraction mode {mode!r}")
    parser = _Extractor(mode)
    parser.feed(html)
    parser.close()
    # Collapse whitespace; keep order, which preserves where a payload appears.
    return re.sub(r"\s+", " ", " ".join(parser.parts)).strip()


def page_title(html: str) -> str:
    match = re.search(r"<title>(.*?)</title>", html, re.I | re.S)
    return match.group(1).strip() if match else ""
