"""Experiment grid and runner.

A run is one cell of ``model x scenario x defense x repetition``. For every cell
the harness builds the in-process lab, connects the agent to the MCP Browser,
runs the tool loop and scores the outcome from observable evidence. Rows are
written to a JSONL file that ``report`` later aggregates.

The in-process path models the network faithfully (resolver, TLS policy,
collector) through :mod:`mcplab.labcore`, so a run needs only a model backend -
no Docker, no real network - which is what keeps CI and the headline results
reproducible.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from dataclasses import asdict, dataclass
from pathlib import Path

from .agent import Agent, make_agent, system_prompt
from .attacks import markers_for
from .browser import BrowserCore
from .labcore import Collector, Lab
from .scenarios import Scenario
from .scoring import score_run
from .stats import stable_seed


@dataclass(frozen=True)
class Defense:
    """A named combination of the three defense dimensions."""

    name: str
    system_arm: str  # plain | warn
    extraction: str  # reader | markdown | raw
    provenance: bool


# The headline defense ladder, from most exposed to fully defended.
DEFENSES: tuple[Defense, ...] = (
    Defense("none", "plain", "raw", False),
    Defense("reader", "plain", "reader", False),
    Defense("warn", "warn", "raw", False),
    Defense("provenance", "plain", "raw", True),
    Defense("all", "warn", "reader", True),
)
DEFENSES_BY_NAME = {d.name: d for d in DEFENSES}


@dataclass
class Row:
    """One scored run, serialised to JSONL."""

    model: str
    scenario: str
    family: str
    objective: str
    vector: str
    defense: str
    system_arm: str
    extraction: str
    provenance: bool
    rep: int
    run_id: str
    utility: bool
    attack_success: bool
    corrected: bool
    steps: int
    tool_calls: int
    detail: str


def _primary_vector(scenario: Scenario) -> str:
    injected = scenario.injected_pages()
    return injected[0].inject.vector if injected else "none"


def run_cell(
    agent: Agent,
    model_label: str,
    scenario: Scenario,
    defense: Defense,
    rep: int,
) -> Row:
    """Execute and score one cell."""
    run_id = f"{stable_seed(model_label, scenario.id, defense.name, rep):08x}"
    markers = markers_for(
        run_id, attacker_domain=scenario.attacker_domain, true_version=scenario.true_version
    )
    collector = Collector()
    lab = Lab(scenario, markers, collector)
    browser = BrowserCore(lab, extraction=defense.extraction, provenance=defense.provenance)
    system = system_prompt(defense.system_arm, markers)
    result = agent.run(scenario, markers, browser, system)
    score = score_run(scenario, markers, result.final_text, browser.calls, collector.hits)
    return Row(
        model=model_label,
        scenario=scenario.id,
        family=scenario.family,
        objective=scenario.objective,
        vector=_primary_vector(scenario),
        defense=defense.name,
        system_arm=defense.system_arm,
        extraction=defense.extraction,
        provenance=defense.provenance,
        rep=rep,
        run_id=run_id,
        utility=score.utility,
        attack_success=score.attack_success,
        corrected=score.corrected,
        steps=result.steps,
        tool_calls=len(browser.calls),
        detail=score.detail,
    )


def run_grid(
    scenarios: Iterable[Scenario],
    *,
    backend: str,
    model: str = "",
    base_url: str = "",
    defenses: Iterable[Defense] = DEFENSES,
    reps: int = 1,
) -> Iterator[Row]:
    """Yield a scored :class:`Row` for every cell of the grid."""
    model_label = f"{backend}:{model}" if model else backend
    agent = make_agent(backend, model=model, base_url=base_url)
    scenarios = list(scenarios)
    defenses = list(defenses)
    for scenario in scenarios:
        for defense in defenses:
            for rep in range(reps):
                yield run_cell(agent, model_label, scenario, defense, rep)


def write_jsonl(rows: Iterable[Row], path: str | Path) -> int:
    """Write rows to ``path`` as JSONL; return the count."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with out.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(asdict(row), ensure_ascii=False) + "\n")
            n += 1
    return n


def read_jsonl(path: str | Path) -> list[dict]:
    """Read a JSONL results file into a list of dicts."""
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line]
