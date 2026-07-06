"""Command-line entry point.

    python -m selfdeploy analyze \
        --vertical injection_molding \
        --requirement-file examples/requirement.txt \
        --evidence-file examples/injection_molding_evidence.json \
        --html out.html

Wires together: decompose (requirement -> ought-graph) -> ground (against
evidence) -> report (gap map). The LLM mapping stage is off by default so the
whole pipeline runs deterministically and offline.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .decompose import build_graph
from .grounding import Evidence, Signal, ground
from .report import html_report, text_report
from .templates import VERTICALS


def load_evidence(path: Path) -> Evidence:
    data = json.loads(path.read_text(encoding="utf-8"))
    signals = [
        Signal(
            id=s["id"],
            kind=s.get("kind", "data"),
            tags=s.get("tags", []),
            description=s.get("description", ""),
        )
        for s in data.get("signals", [])
    ]
    return Evidence(signals=signals, judgment_owners=data.get("judgment_owners", {}))


def cmd_analyze(args: argparse.Namespace) -> int:
    vertical = VERTICALS.get(args.vertical)
    if vertical is None:
        print(f"unknown vertical: {args.vertical}. known: {', '.join(VERTICALS)}", file=sys.stderr)
        return 2

    if args.requirement_file:
        requirement = Path(args.requirement_file).read_text(encoding="utf-8")
    elif args.requirement:
        requirement = args.requirement
    else:
        print("provide --requirement or --requirement-file", file=sys.stderr)
        return 2

    evidence = load_evidence(Path(args.evidence_file)) if args.evidence_file else Evidence()

    graph = build_graph(requirement, vertical)
    ground(graph, evidence)

    print(text_report(graph))

    if args.html:
        Path(args.html).write_text(html_report(graph), encoding="utf-8")
        print(f"\nHTML gap map -> {args.html}", file=sys.stderr)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="selfdeploy", description="Ought-first measurement-grounding engine")
    sub = parser.add_subparsers(dest="command", required=True)

    analyze = sub.add_parser("analyze", help="requirement -> ought-graph -> gap map")
    analyze.add_argument("--vertical", default="injection_molding")
    analyze.add_argument("--requirement")
    analyze.add_argument("--requirement-file")
    analyze.add_argument("--evidence-file")
    analyze.add_argument("--html", help="write an HTML gap map to this path")
    analyze.set_defaults(func=cmd_analyze)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
