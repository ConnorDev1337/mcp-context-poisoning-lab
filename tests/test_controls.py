"""End-to-end runs with the deterministic control agents.

The positive control (``naive``) obeys every injection, so with the most exposed
defense every scenario's scorer must fire. The negative control (``careful``)
ignores injections, so no scorer fires and the task still succeeds. These two
bounds validate the whole pipeline (lab, browser, agent loop, scoring) without a
model.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mcplab import scenarios
from mcplab.agent import make_agent
from mcplab.runner import DEFENSES_BY_NAME, run_cell

SCEN_DIR = Path(__file__).resolve().parents[1] / "lab" / "scenarios"
ALL = scenarios.load_dir(SCEN_DIR)
NONE = DEFENSES_BY_NAME["none"]
ALL_DEF = DEFENSES_BY_NAME["all"]


@pytest.mark.parametrize("scenario", ALL, ids=lambda s: s.id)
def test_naive_is_compromised_under_no_defense(scenario):
    # The TLS-verify DNS scenario is the one case where even the obedient agent
    # cannot be compromised: the hijacked fetch fails before any payload is read.
    agent = make_agent("naive")
    row = run_cell(agent, "naive", scenario, NONE, 0)
    if scenario.id == "f6-dns-verify":
        assert not row.attack_success
    else:
        assert row.attack_success, row.detail


@pytest.mark.parametrize("scenario", ALL, ids=lambda s: s.id)
def test_careful_is_never_compromised(scenario):
    agent = make_agent("careful")
    row = run_cell(agent, "careful", scenario, NONE, 0)
    assert not row.attack_success, row.detail
    assert row.utility, row.detail


def test_full_defense_reduces_naive_attack_rate():
    agent = make_agent("naive")
    exposed = [run_cell(agent, "naive", s, NONE, 0).attack_success for s in ALL]
    defended = [run_cell(agent, "naive", s, ALL_DEF, 0).attack_success for s in ALL]
    assert sum(defended) < sum(exposed)


def test_reader_mode_strips_hidden_injection():
    scenario = scenarios.load_file(SCEN_DIR / "f2-indirect-injection.yaml")
    agent = make_agent("naive")
    assert run_cell(agent, "naive", scenario, NONE, 0).attack_success
    assert not run_cell(agent, "naive", scenario, DEFENSES_BY_NAME["reader"], 0).attack_success


def test_tls_verify_blocks_dns_hijack():
    plain = scenarios.load_file(SCEN_DIR / "f6-dns-plain.yaml")
    verify = scenarios.load_file(SCEN_DIR / "f6-dns-verify.yaml")
    agent = make_agent("naive")
    assert run_cell(agent, "naive", plain, NONE, 0).attack_success
    assert not run_cell(agent, "naive", verify, NONE, 0).attack_success
