"""Command-line interface: ``mcplab list | run | report | demo | serve``."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from . import scenarios as scen
from .attacks import OBJECTIVES, VECTORS
from .report import build_csv, build_markdown
from .runner import DEFENSES_BY_NAME, read_jsonl, run_grid, write_jsonl

DEFAULT_SCENARIOS = os.environ.get("MCPLAB_SCENARIOS", "lab/scenarios")


def _load(scenarios_dir: str) -> list:
    path = Path(scenarios_dir)
    if not path.exists():
        raise SystemExit(f"scenario directory not found: {path} (set --scenarios)")
    return scen.load_dir(path)


def cmd_list(args: argparse.Namespace) -> int:
    loaded = _load(args.scenarios)
    print(f"{len(loaded)} scenarios in {args.scenarios}:\n")
    for s in loaded:
        inj = ",".join(sorted({p.inject.vector for p in s.injected_pages()})) or "-"
        print(f"  {s.id:28s} {s.family}  obj={s.objective:12s} vectors={inj}")
    print(f"\nobjectives: {', '.join(OBJECTIVES)}")
    print(f"vectors:    {', '.join(sorted(VECTORS))}, tool_description")
    print(f"defenses:   {', '.join(DEFENSES_BY_NAME)}")
    return 0


def _run(args: argparse.Namespace) -> int:
    loaded = _load(args.scenarios)
    defenses = (
        [DEFENSES_BY_NAME[name] for name in args.defenses.split(",")]
        if args.defenses
        else list(DEFENSES_BY_NAME.values())
    )
    rows = run_grid(
        loaded,
        backend=args.backend,
        model=args.model,
        base_url=args.base_url,
        defenses=defenses,
        reps=args.reps,
    )
    n = write_jsonl(rows, args.out)
    print(f"wrote {n} runs to {args.out}")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    rows = read_jsonl(args.infile)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.md").write_text(build_markdown(rows), encoding="utf-8", newline="\n")
    (out_dir / "summary.csv").write_text(build_csv(rows), encoding="utf-8", newline="\n")
    print(f"wrote {out_dir / 'report.md'} and {out_dir / 'summary.csv'}")
    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    """Run both mock agents over the bundled scenarios and write a report."""
    loaded = _load(args.scenarios)
    out_dir = Path(args.out_dir)
    rows = []
    for backend in ("naive", "careful"):
        rows.extend(run_grid(loaded, backend=backend))
    write_jsonl(rows, out_dir / "raw.jsonl")
    dicts = [r.__dict__ for r in rows]
    (out_dir / "report.md").write_text(build_markdown(dicts), encoding="utf-8", newline="\n")
    (out_dir / "summary.csv").write_text(build_csv(dicts), encoding="utf-8", newline="\n")
    print(f"demo: {len(rows)} runs -> {out_dir}/report.md")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:  # pragma: no cover - needs services extra
    from .browser import serve

    serve(host=args.host, port=args.port)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mcplab", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("list", help="list scenarios, objectives and vectors")
    p.add_argument("--scenarios", default=DEFAULT_SCENARIOS)
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("run", help="run the experiment grid against a backend")
    p.add_argument("--scenarios", default=DEFAULT_SCENARIOS)
    p.add_argument("--backend", required=True, help="naive|careful|ollama|openai|anthropic|gemini")
    p.add_argument("--model", default="")
    p.add_argument("--base-url", default="")
    p.add_argument("--defenses", default="", help="comma-separated subset of defense names")
    p.add_argument("--reps", type=int, default=1)
    p.add_argument("--out", default="runs/raw.jsonl")
    p.set_defaults(func=_run)

    p = sub.add_parser("report", help="aggregate a results file into report.md + summary.csv")
    p.add_argument("--in", dest="infile", default="runs/raw.jsonl")
    p.add_argument("--out-dir", default="runs")
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("demo", help="run the mock controls over bundled scenarios")
    p.add_argument("--scenarios", default=DEFAULT_SCENARIOS)
    p.add_argument("--out-dir", default="runs")
    p.set_defaults(func=cmd_demo)

    p = sub.add_parser("serve-browser", help="serve the MCP Browser (needs the services extra)")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8000)
    p.set_defaults(func=cmd_serve)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
