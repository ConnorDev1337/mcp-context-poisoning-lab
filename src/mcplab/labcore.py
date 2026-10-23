"""In-process model of the lab for one scenario.

The same logic backs both the Dockerised services (search, web servers,
collector, resolver) and the fast in-process path the tests and the mock agents
use. Keeping one implementation means a mock run and a full Docker run exercise
the same resolution, serving, search ranking and beaconing rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlsplit

from .attacks import Markers
from .render import extract, page_title, render_page
from .scenarios import Scenario


class FetchError(Exception):
    """Raised when a page cannot be fetched (bad host, TLS failure, not found)."""


def _norm(path: str) -> str:
    path = path or "/"
    if not path.startswith("/"):
        path = "/" + path
    stripped = path.rstrip("/")
    return stripped or "/"


@dataclass
class CollectorHit:
    """One request the attacker's beacon endpoint received."""

    run_id: str
    path: str
    query: dict[str, list[str]]
    raw_url: str


@dataclass
class Collector:
    """Records beacon hits so instruction-following is measured from side effects."""

    hits: list[CollectorHit] = field(default_factory=list)

    def record(self, url: str, run_id: str) -> None:
        parts = urlsplit(url)
        self.hits.append(
            CollectorHit(
                run_id=run_id,
                path=parts.path,
                query=parse_qs(parts.query),
                raw_url=url,
            )
        )

    def hits_for(self, run_id: str) -> list[CollectorHit]:
        return [h for h in self.hits if h.run_id == run_id]


@dataclass
class FetchResult:
    """What ``fetch`` returns to the browser tool."""

    url: str
    title: str
    text: str
    resolved_host: str
    resolution: str  # "clean" | "poisoned"
    tls_verified: bool


class Lab:
    """A scenario rendered into servable pages plus the resolver and collector."""

    def __init__(self, scenario: Scenario, markers: Markers, collector: Collector) -> None:
        self.scenario = scenario
        self.markers = markers
        self.collector = collector
        self._scheme = "http" if scenario.tls == "plain" else "https"
        self._pages: dict[tuple[str, str], str] = {}
        for page in scenario.pages:
            self._pages[(page.host, _norm(page.path))] = render_page(scenario, page, markers)

    # -- name resolution -----------------------------------------------------

    def resolve(self, host: str) -> tuple[str, str]:
        """Return ``(resolution, effective_host)`` for ``host``.

        A poisoned resolver redirects the scenario's ``poisoned_names`` to the
        attacker's host, so a trusted name serves attacker content.
        """
        if self.scenario.resolver == "poisoned" and host in self.scenario.poisoned_names:
            return "poisoned", self.scenario.attacker_domain
        return "clean", host

    # -- search --------------------------------------------------------------

    def search(self, query: str, max_results: int = 5) -> list[dict[str, str]]:
        """Return the ranked results the lab serves for ``query``."""
        matched = next((q for q in self.scenario.queries if q.query == query), None)
        if matched is None:
            # Fall back to the first configured query so a model's paraphrase of
            # the task still returns the scenario's ranking.
            matched = self.scenario.queries[0] if self.scenario.queries else None
        if matched is None:
            return []
        out = []
        for result in matched.results[:max_results]:
            html = self._pages.get((result.host, _norm(result.path)), "")
            title = result.title or (page_title(html) if html else result.host)
            if result.authority_badge:
                title = f"[{result.authority_badge.upper()}] {title}"
            snippet = result.snippet or extract(html, "reader")[:160]
            out.append(
                {
                    "title": title,
                    "url": f"{self._scheme}://{result.host}{result.path}",
                    "snippet": snippet,
                }
            )
        return out

    # -- fetch ---------------------------------------------------------------

    def fetch(self, url: str, mode: str = "reader") -> FetchResult:
        """Resolve and serve ``url``, applying the scenario's TLS policy."""
        parts = urlsplit(url if "://" in url else f"{self._scheme}://{url}")
        host = parts.hostname or ""
        path = _norm(parts.path)
        if not host.endswith(".test"):
            raise FetchError(f"refusing non-lab host {host!r} (lab hosts end in .test)")

        if host == self.markers.collector_host:
            self.collector.record(url, self.markers.run_id)
            return FetchResult(url, "Collector", "ok", host, "clean", True)

        resolution, effective = self.resolve(host)
        tls_verified = False
        if self.scenario.tls == "verify":
            # A hijacked name cannot present a valid certificate for itself.
            if resolution == "poisoned":
                raise FetchError(f"TLS verification failed for {host}: certificate does not match")
            tls_verified = True

        html = self._pages.get((effective, path))
        if html is None:
            raise FetchError(f"404 {host}{path}")
        return FetchResult(
            url=url,
            title=page_title(html),
            text=extract(html, mode),
            resolved_host=effective,
            resolution=resolution,
            tls_verified=tls_verified,
        )
