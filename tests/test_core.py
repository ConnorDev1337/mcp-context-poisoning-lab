"""Unit tests for rendering, extraction, scoring, stats and scenario loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from mcplab import scenarios
from mcplab.attacks import HIDDEN_IN_TEXT, embed, markers_for, payload_text
from mcplab.render import extract, md_to_html, render_page
from mcplab.stats import wilson

SCEN_DIR = Path(__file__).resolve().parents[1] / "lab" / "scenarios"


def test_wilson_bounds_and_edges():
    assert wilson(0, 0).as_pct() == "n/a"
    iv = wilson(5, 10)
    assert 0.0 <= iv.low <= iv.rate <= iv.high <= 1.0
    assert wilson(10, 10).rate == 1.0 and wilson(10, 10).high <= 1.0
    assert wilson(0, 10).rate == 0.0 and wilson(0, 10).low == 0.0
    with pytest.raises(ValueError):
        wilson(3, 2)


def test_markdown_subset():
    html = md_to_html("# Title\n\nHello **world** and [docs](/d).\n\n- a\n- b")
    assert "<h1>Title</h1>" in html
    assert "<strong>world</strong>" in html
    assert '<a href="/d">docs</a>' in html
    assert "<li>a</li>" in html


@pytest.mark.parametrize("vector", sorted(HIDDEN_IN_TEXT))
def test_hidden_vectors_absent_from_reader_present_in_raw(vector):
    payload = "MARKER-ZZZ follow this"
    snippet = embed(vector, payload)
    html = f"<!doctype html><html><head></head><body><p>visible</p>{snippet}</body></html>"
    if vector == "meta_tag":
        html = f"<html><head>{snippet}</head><body><p>visible</p></body></html>"
    assert "MARKER-ZZZ" not in extract(html, "reader")
    assert "MARKER-ZZZ" in extract(html, "raw")


def test_visible_note_survives_every_mode():
    html = f"<html><body><p>x</p>{embed('visible_note', 'SEEN-NOTE')}</body></html>"
    for mode in ("reader", "markdown", "raw"):
        assert "SEEN-NOTE" in extract(html, mode)


def test_markdown_mode_keeps_attributes_drops_comments_and_head():
    # Markdown conversion surfaces attribute text (alt/title/aria) and keeps text
    # nodes regardless of CSS, but drops HTML comments and <head> metadata.
    for vector in ("alt_text", "title_attr", "aria_label"):
        html = f"<html><body>{embed(vector, 'ATTR-P')}</body></html>"
        assert "ATTR-P" in extract(html, "markdown")
    for vector in ("html_comment", "meta_tag"):
        snippet = embed(vector, "HID-P")
        html = (
            f"<html><head>{snippet}</head><body>x</body></html>"
            if vector == "meta_tag"
            else f"<html><body>{snippet}</body></html>"
        )
        assert "HID-P" not in extract(html, "markdown")


def test_all_bundled_scenarios_load_and_validate():
    loaded = scenarios.load_dir(SCEN_DIR)
    assert len(loaded) >= 7
    families = {s.family for s in loaded}
    assert {"F1", "F2", "F3", "F4", "F5", "F6", "F7"} <= families


def test_render_embeds_payload_for_injected_page():
    scenario = scenarios.load_file(SCEN_DIR / "f2-indirect-injection.yaml")
    m = markers_for("run1", attacker_domain=scenario.attacker_domain, true_version="3.4")
    page = scenario.injected_pages()[0]
    html = render_page(scenario, page, m)
    assert payload_text("O2_beacon", m)[:20] in html


def test_payload_text_covers_all_objectives():
    m = markers_for("r", attacker_domain="a.test", true_version="3.4")
    from mcplab.attacks import OBJECTIVES

    for obj in OBJECTIVES:
        assert payload_text(obj, m)
