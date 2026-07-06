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
from .evolve import classify_requirement, classify_signal
from .grounding import Evidence, Signal, ground
from .interview import Answer, generate_questions, run_round
from .report import html_report, text_report
from .templates import VERTICALS


def _mapper(args: argparse.Namespace):
    """Build the optional Claude requirement mapper, or None for deterministic matching."""
    if getattr(args, "llm", False):
        from .llm import ClaudeRequirementMapper

        return ClaudeRequirementMapper()
    return None


def _read_requirement(args: argparse.Namespace) -> str | None:
    if getattr(args, "requirement_file", None):
        return Path(args.requirement_file).read_text(encoding="utf-8")
    if getattr(args, "requirement", None):
        return args.requirement
    return None


def load_answers(path: Path) -> list[Answer]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [
        Answer(
            contract_id=a["contract_id"],
            signal_id=a.get("signal_id"),
            data=a.get("data", False),
            owner=a.get("owner"),
            description=a.get("description", ""),
        )
        for a in data.get("answers", [])
    ]


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

    graph = build_graph(requirement, vertical, _mapper(args))
    ground(graph, evidence)

    print(text_report(graph))

    if args.html:
        Path(args.html).write_text(html_report(graph), encoding="utf-8")
        print(f"\nHTML gap map -> {args.html}", file=sys.stderr)
    return 0


def cmd_questions(args: argparse.Namespace) -> int:
    vertical = VERTICALS.get(args.vertical)
    if vertical is None:
        print(f"unknown vertical: {args.vertical}", file=sys.stderr)
        return 2
    requirement = _read_requirement(args)
    if requirement is None:
        print("provide --requirement or --requirement-file", file=sys.stderr)
        return 2
    evidence = load_evidence(Path(args.evidence_file)) if args.evidence_file else Evidence()
    graph = ground(build_graph(requirement, vertical, _mapper(args)), evidence)
    questions = generate_questions(graph)
    if not questions:
        print("빨간 칸 없음 — 모든 계약이 착지했다.")
        return 0
    print(f"강제 질문 {len(questions)}개 (타입 미닫힘에서 자동 생성):\n")
    for i, q in enumerate(questions, 1):
        print(f"[{i}] ({q.gap}) {q.label}")
        print(f"    Q: {q.prompt}")
        print(f"    닫힘 조건: {q.closes_with}\n")
    return 0


def cmd_interview(args: argparse.Namespace) -> int:
    vertical = VERTICALS.get(args.vertical)
    if vertical is None:
        print(f"unknown vertical: {args.vertical}", file=sys.stderr)
        return 2
    requirement = _read_requirement(args)
    if requirement is None:
        print("provide --requirement or --requirement-file", file=sys.stderr)
        return 2
    evidence = load_evidence(Path(args.evidence_file)) if args.evidence_file else Evidence()
    answers = load_answers(Path(args.answers_file)) if args.answers_file else []

    graph, new_evidence, rnd = run_round(requirement, vertical, evidence, answers, _mapper(args))

    print("빨간 칸 채우기 라운드 / interview round")
    print(f"  before: red {rnd.before.red}  (밀도 {rnd.before.red_density:.0%})")
    print(f"  적용한 답변: {len(answers)}개")
    print(f"  after : red {rnd.after.red}  (밀도 {rnd.after.red_density:.0%})   → 닫은 빨간 칸: {rnd.red_closed}")
    print()
    print(text_report(graph))
    if args.html:
        Path(args.html).write_text(html_report(graph), encoding="utf-8")
        print(f"\nHTML gap map -> {args.html}", file=sys.stderr)
    return 0


def cmd_classify(args: argparse.Namespace) -> int:
    vertical = VERTICALS.get(args.vertical)
    if vertical is None:
        print(f"unknown vertical: {args.vertical}", file=sys.stderr)
        return 2
    requirement = _read_requirement(args)
    if requirement is None:
        print("provide --requirement or --requirement-file (the current model)", file=sys.stderr)
        return 2
    graph = build_graph(requirement, vertical, _mapper(args))

    if args.signal_file:
        data = json.loads(Path(args.signal_file).read_text(encoding="utf-8"))
        signal = Signal(id=data["id"], kind=data.get("kind", "data"), tags=data.get("tags", []))
        verdict = classify_signal(graph, signal)
        subject = f"신호 {signal.id} (tags: {signal.tags})"
    elif args.new_requirement:
        verdict = classify_requirement(args.new_requirement, vertical, graph)
        subject = f"새 요구: {args.new_requirement}"
    else:
        print("provide --signal-file or --new-requirement", file=sys.stderr)
        return 2

    speed_ko = {"continuous": "상시 입력 (가벼운 게이트)", "promote": "승급 판정 (사람 결정)", "redesign": "재설계 (무거운 게이트)"}
    print(f"{subject}")
    print(f"  → {speed_ko.get(verdict.speed, verdict.speed)}")
    print(f"  이유: {verdict.reason}")
    if verdict.matched_tags:
        print(f"  기존 계약과 맞는 태그: {verdict.matched_tags}")
    if verdict.novel_tags:
        print(f"  새 태그: {verdict.novel_tags}")
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
    analyze.add_argument("--llm", action="store_true", help="use Claude to map requirement->KPIs (needs ANTHROPIC creds)")
    analyze.set_defaults(func=cmd_analyze)

    questions = sub.add_parser("questions", help="forced questions generated from red cells")
    questions.add_argument("--vertical", default="injection_molding")
    questions.add_argument("--requirement")
    questions.add_argument("--requirement-file")
    questions.add_argument("--evidence-file")
    questions.add_argument("--llm", action="store_true")
    questions.set_defaults(func=cmd_questions)

    interview = sub.add_parser("interview", help="apply answers to red cells and re-ground")
    interview.add_argument("--vertical", default="injection_molding")
    interview.add_argument("--requirement")
    interview.add_argument("--requirement-file")
    interview.add_argument("--evidence-file")
    interview.add_argument("--answers-file")
    interview.add_argument("--html")
    interview.add_argument("--llm", action="store_true")
    interview.set_defaults(func=cmd_interview)

    classify = sub.add_parser("classify", help="dual-speed: is a change 상시입력 or 재설계?")
    classify.add_argument("--vertical", default="injection_molding")
    classify.add_argument("--requirement", help="the current model's requirement")
    classify.add_argument("--requirement-file")
    classify.add_argument("--signal-file", help="a new evidence signal JSON {id,kind,tags}")
    classify.add_argument("--new-requirement", help="a new manager requirement to classify")
    classify.add_argument("--llm", action="store_true")
    classify.set_defaults(func=cmd_classify)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
