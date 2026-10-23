"""Aggregate raw run rows into a Markdown report and a machine-readable CSV.

Every rate is a proportion with a 95% Wilson interval. The report answers the
lab's questions: how often does each model obey injected instructions, which
defense reduces that without destroying task utility, which hidden carriers
survive which extraction mode, and how each attack objective fares.
"""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from collections.abc import Iterable

from .runner import DEFENSES
from .stats import Interval, wilson

_DEFENSE_ORDER = [d.name for d in DEFENSES]


def _rate(rows: list[dict], key: str) -> Interval:
    total = len(rows)
    succ = sum(1 for r in rows if r[key])
    return wilson(succ, total)


def _group(rows: Iterable[dict], *keys: str) -> dict[tuple, list[dict]]:
    out: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        out[tuple(row[k] for k in keys)].append(row)
    return out


def _defense_sort(name: str) -> int:
    return _DEFENSE_ORDER.index(name) if name in _DEFENSE_ORDER else len(_DEFENSE_ORDER)


def build_markdown(rows: list[dict]) -> str:
    if not rows:
        return "# Results\n\n(no runs)\n"
    models = sorted({r["model"] for r in rows})
    defenses = sorted({r["defense"] for r in rows}, key=_defense_sort)
    out: list[str] = ["# Results\n"]
    out.append(
        f"{len(rows)} runs | {len(models)} model(s) | "
        f"{len({r['scenario'] for r in rows})} scenarios\n"
    )

    # 1. Headline: ASR and utility by model x defense.
    out.append("## Attack success and utility by defense\n")
    out.append(
        "ASR = attack success rate (lower is safer). "
        "Utility = task completed (higher is better). 95% Wilson intervals.\n"
    )
    out.append("| model | defense | ASR | utility |")
    out.append("| --- | --- | --- | --- |")
    by_md = _group(rows, "model", "defense")
    for model in models:
        for defense in defenses:
            cell = by_md.get((model, defense))
            if not cell:
                continue
            asr = _rate(cell, "attack_success")
            util = _rate(cell, "utility")
            out.append(f"| {model} | {defense} | {asr.as_pct()} | {util.as_pct()} |")
    out.append("")

    # 2. ASR by attack family (most exposed defense = 'none').
    out.append("## Attack success by family (defense = none)\n")
    out.append("| model | family | ASR |")
    out.append("| --- | --- | --- |")
    exposed = [r for r in rows if r["defense"] == "none"]
    for (model, family), cell in sorted(_group(exposed, "model", "family").items()):
        out.append(f"| {model} | {family} | {_rate(cell, 'attack_success').as_pct()} |")
    out.append("")

    # 3. Vector survival across extraction modes (positive control preferred).
    control = [r for r in rows if r["model"].endswith("naive") or r["model"] == "naive"]
    survival_src = control or rows
    out.append("## Hidden-vector survival by extraction mode\n")
    out.append(
        "ASR for each carrier under each extraction mode"
        + (" (positive control)" if control else "")
        + ".\n"
    )
    modes = sorted({r["extraction"] for r in survival_src})
    vectors = sorted({r["vector"] for r in survival_src if r["vector"] != "none"})
    out.append("| vector | " + " | ".join(modes) + " |")
    out.append("| --- |" + " --- |" * len(modes))
    by_vm = _group(survival_src, "vector", "extraction")
    for vector in vectors:
        cells = []
        for mode in modes:
            group = by_vm.get((vector, mode))
            cells.append(_rate(group, "attack_success").as_pct() if group else "n/a")
        out.append(f"| {vector} | " + " | ".join(cells) + " |")
    out.append("")

    # 4. ASR by objective x defense.
    out.append("## Attack success by objective and defense\n")
    objectives = sorted({r["objective"] for r in rows})
    out.append("| objective | " + " | ".join(defenses) + " |")
    out.append("| --- |" + " --- |" * len(defenses))
    by_od = _group(rows, "objective", "defense")
    for obj in objectives:
        cells = []
        for defense in defenses:
            group = by_od.get((obj, defense))
            cells.append(_rate(group, "attack_success").as_pct() if group else "n/a")
        out.append(f"| {obj} | " + " | ".join(cells) + " |")
    out.append("")
    return "\n".join(out)


def build_csv(rows: list[dict]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["model", "defense", "metric", "rate", "low", "high", "successes", "total"])
    for (model, defense), cell in sorted(_group(rows, "model", "defense").items()):
        for metric in ("attack_success", "utility"):
            iv = _rate(cell, metric)
            writer.writerow(
                [
                    model,
                    defense,
                    metric,
                    f"{iv.rate:.4f}",
                    f"{iv.low:.4f}",
                    f"{iv.high:.4f}",
                    iv.successes,
                    iv.total,
                ]
            )
    return buf.getvalue()
