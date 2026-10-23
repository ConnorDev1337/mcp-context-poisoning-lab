#!/usr/bin/env python3
"""Run the lab benchmark against multiple Ollama models sequentially.

Usage:
    python scripts/bench_multi.py
    python scripts/bench_multi.py --models qwen2.5:7b-instruct,llama3.1:8b --reps 5

Each model's results are written to runs/<model>/report.md and summary.csv, plus
a combined report in runs/combined/report.md that merges all runs for cross-model
comparison.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add the project root to the path so we can import mcplab.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mcplab.report import build_csv, build_markdown  # noqa: E402
from mcplab.runner import run_grid, write_jsonl  # noqa: E402
from mcplab.scenarios import load_dir  # noqa: E402

# Tool-capable Ollama tags (this harness drives the agent through tool calls, so
# a model without tool support is rejected by Ollama and its cells are skipped).
DEFAULT_MODELS = [
    "qwen2.5:7b-instruct",
    "llama3.1:8b",
    "mistral:7b",
]

DEFAULT_SCENARIOS = "lab/scenarios"
DEFAULT_REPS = 10
DEFAULT_BASE_URL = "http://localhost:11434/v1"


def run_model(
    model: str,
    scenarios_dir: str,
    base_url: str,
    reps: int,
    out_root: Path,
) -> list[dict]:
    """Run all scenarios against one model and write per-model results."""
    print(f"\n{'=' * 60}")
    print(f"  Model: {model}   ({reps} reps)")
    print(f"{'=' * 60}\n")

    scenarios = load_dir(scenarios_dir)
    rows = list(run_grid(scenarios, backend="ollama", model=model, base_url=base_url, reps=reps))
    model_slug = model.replace(":", "_").replace("/", "_")
    model_dir = out_root / model_slug
    model_dir.mkdir(parents=True, exist_ok=True)

    raw_path = model_dir / "raw.jsonl"
    write_jsonl(rows, raw_path)
    dicts = [r.__dict__ if hasattr(r, "__dict__") else r for r in rows]
    (model_dir / "report.md").write_text(build_markdown(dicts), encoding="utf-8", newline="\n")
    (model_dir / "summary.csv").write_text(build_csv(dicts), encoding="utf-8", newline="\n")
    print(f"  -> {len(rows)} runs written to {model_dir}/")
    return dicts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--models",
        default=",".join(DEFAULT_MODELS),
        help="comma-separated list of Ollama model tags",
    )
    parser.add_argument("--scenarios", default=DEFAULT_SCENARIOS)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--reps", type=int, default=DEFAULT_REPS)
    parser.add_argument("--out", default="runs")
    args = parser.parse_args(argv)

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    out_root = Path(args.out)
    all_rows: list[dict] = []

    # Also run the deterministic controls for comparison.
    print("\n--- Running deterministic controls (naive + careful) ---")
    scenarios = load_dir(args.scenarios)
    for backend in ("naive", "careful"):
        rows = list(run_grid(scenarios, backend=backend))
        dicts = [r.__dict__ for r in rows]
        all_rows.extend(dicts)

    for model in models:
        try:
            dicts = run_model(model, args.scenarios, args.base_url, args.reps, out_root)
            all_rows.extend(dicts)
        except Exception as exc:
            print(f"\n  !! Failed for {model}: {exc}\n")
            continue

    # Write combined report.
    combined_dir = out_root / "combined"
    combined_dir.mkdir(parents=True, exist_ok=True)
    (combined_dir / "report.md").write_text(
        build_markdown(all_rows), encoding="utf-8", newline="\n"
    )
    (combined_dir / "summary.csv").write_text(build_csv(all_rows), encoding="utf-8", newline="\n")
    combined_raw = combined_dir / "raw.jsonl"
    with combined_raw.open("w", encoding="utf-8", newline="\n") as fh:
        for row in all_rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"\n{'=' * 60}")
    print(f"  Combined report: {combined_dir / 'report.md'}")
    print(f"  {len(all_rows)} total runs across {len(models)} model(s) + controls")
    print(f"{'=' * 60}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
