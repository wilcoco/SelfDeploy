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

from .collectors import (
    collect_all,
    data_source_collector,
    plan_sensing,
    predictive_maintenance_collector,
)
from .decompose import build_graph, build_obligation_graph
from .evolve import classify_requirement, classify_signal
from .grounding import Evidence, Signal, ground, metrics
from .interview import Answer, generate_questions, run_round
from .owners import (
    LLMOwnerResolver,
    assign_owners,
    by_owner,
    manual_resolver,
    org_chart_resolver,
    template_resolver,
)
from .report import html_report, text_report
from .risk import escalate, risk_register
from .templates import VERTICALS


def _clean_line(text: str) -> str:
    return " ".join(text.split())


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
            as_of=s.get("as_of"),
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
    ground(graph, evidence, as_of=args.as_of)

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


def cmd_plan_sensing(args: argparse.Namespace) -> int:
    vertical = VERTICALS.get(args.vertical)
    if vertical is None:
        print(f"unknown vertical: {args.vertical}", file=sys.stderr)
        return 2
    requirement = _read_requirement(args)
    if requirement is None:
        print("provide --requirement or --requirement-file", file=sys.stderr)
        return 2
    evidence = load_evidence(Path(args.evidence_file)) if args.evidence_file else Evidence()
    graph = ground(build_graph(requirement, vertical, _mapper(args)), evidence, as_of=args.as_of)

    plans = plan_sensing(graph)
    sensor = [p for p in plans if not p.human_only]
    human = [p for p in plans if p.human_only]

    print("빨간/미검증 칸 → 말단 센싱 대안\n")
    if sensor:
        print("● 센싱으로 닫을 수 있는 칸:")
        for p in sensor:
            strength = "검증(강)" if p.best_strength == "strong" else "미검증(약)"
            print(f"  ✗ {_clean_line(p.label)}")
            print(f"      후보: {', '.join(p.candidates)}  → {strength}")
    if human:
        print("\n● 센싱 대안 없음 — 인터뷰 게이트(사람)만:")
        for p in human:
            print(f"  ✗ {_clean_line(p.label)}  (은닉 판단/머릿속 — 강제 질문으로)")
    return 0


def cmd_collect(args: argparse.Namespace) -> int:
    vertical = VERTICALS.get(args.vertical)
    if vertical is None:
        print(f"unknown vertical: {args.vertical}", file=sys.stderr)
        return 2
    requirement = _read_requirement(args)
    if requirement is None:
        print("provide --requirement or --requirement-file", file=sys.stderr)
        return 2
    base = load_evidence(Path(args.evidence_file)) if args.evidence_file else Evidence()

    collectors = []
    if args.pm_readings:
        readings = json.loads(Path(args.pm_readings).read_text(encoding="utf-8")).get("readings", [])
        collectors.append(predictive_maintenance_collector(readings))
    if args.erp:
        collectors.append(
            data_source_collector("ERP-tap", ["production_count", "order_due", "shipment_log", "incoming_lot", "finished_lot"])
        )
    if not collectors:
        print("provide --pm-readings and/or --erp", file=sys.stderr)
        return 2

    before = metrics(ground(build_graph(requirement, vertical, _mapper(args)), base, as_of=args.as_of))
    merged = collect_all(collectors, base)
    graph = ground(build_graph(requirement, vertical, _mapper(args)), merged, as_of=args.as_of)
    after = metrics(graph)

    print(f"수집기 {len(collectors)}개 가동 → 신호 {len(merged.signals) - len(base.signals)}개 추가")
    print(f"  before: red {before.red} (밀도 {before.red_density:.0%})")
    print(f"  after : red {after.red} (밀도 {after.red_density:.0%})   → 닫은 빨간 칸: {before.red - after.red}\n")
    print(text_report(graph))
    return 0


def cmd_risk_register(args: argparse.Namespace) -> int:
    vertical = VERTICALS.get(args.vertical)
    if vertical is None:
        print(f"unknown vertical: {args.vertical}", file=sys.stderr)
        return 2
    if not vertical.obligations:
        print(f"'{args.vertical}' 업종에 등록된 의무(책임 표면)가 없음", file=sys.stderr)
        return 2
    evidence = load_evidence(Path(args.evidence_file)) if args.evidence_file else Evidence()
    graph = ground(build_obligation_graph(vertical), evidence, as_of=args.as_of)

    # owner resolution — three options, all fall back to the template role
    if args.org_chart:
        resolver = org_chart_resolver(json.loads(Path(args.org_chart).read_text(encoding="utf-8")))
    elif args.assign:
        resolver = manual_resolver(json.loads(Path(args.assign).read_text(encoding="utf-8")))
    elif args.llm_owners:
        roles = sorted({n.owner_role for n in graph.iter_nodes() if n.owner_role})
        resolver = LLMOwnerResolver(roles, org_description=args.org_desc or "")
    else:
        resolver = template_resolver()
    assign_owners(graph, resolver)

    register = risk_register(graph)
    ceo, ops = escalate(register, args.top)

    def line(it):
        sens = "사람만" if it.human_only else "센싱가능"
        who = f" [{it.owner}]" if it.owner else ""
        return f"  [risk {it.risk:.2f}] (파장 {it.severity:.2f} × {it.grade.value}){who} {_clean_line(it.label)}  — {sens}"

    print(f"대표 리스크 레지스터 — {vertical.name} 책임 표면 (파장 × 미착지 순)\n")

    if args.by_owner:
        print(f"● 오너별 라우팅 (대표 escalation 상위 {len(ceo)}는 ★):")
        ceo_ids = {it.contract_id for it in ceo}
        for owner, items in sorted(by_owner(register).items(), key=lambda kv: -max(i.risk for i in kv[1])):
            print(f"\n  ▸ {owner} — {len(items)}건:")
            for it in items:
                star = "★" if it.contract_id in ceo_ids else " "
                print(f"   {star} {line(it).strip()}")
        return 0

    print(f"● 대표 escalation (상위 {len(ceo)} — 오늘 밤 못 자는 순서):")
    for it in ceo:
        print(line(it))
    if ops:
        print(f"\n● 운영층 worklist (나머지 {len(ops)}):")
        for it in ops:
            print(line(it))
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
    analyze.add_argument("--as-of", type=float, default=None, help="evaluation time (tick); stale data groundings decay to UNVERIFIED")
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

    plan = sub.add_parser("plan-sensing", help="map red cells to edge sensing alternatives")
    plan.add_argument("--vertical", default="injection_molding")
    plan.add_argument("--requirement")
    plan.add_argument("--requirement-file")
    plan.add_argument("--evidence-file")
    plan.add_argument("--as-of", type=float, default=None)
    plan.add_argument("--llm", action="store_true")
    plan.set_defaults(func=cmd_plan_sensing)

    collect = sub.add_parser("collect", help="run edge collectors, merge signals, re-ground")
    collect.add_argument("--vertical", default="injection_molding")
    collect.add_argument("--requirement")
    collect.add_argument("--requirement-file")
    collect.add_argument("--evidence-file")
    collect.add_argument("--pm-readings", help="predictive-maintenance readings JSON {readings:[{device,ts,state}]}")
    collect.add_argument("--erp", action="store_true", help="tap ERP for lot/count/shipment tags")
    collect.add_argument("--as-of", type=float, default=None)
    collect.add_argument("--llm", action="store_true")
    collect.set_defaults(func=cmd_collect)

    risk = sub.add_parser("risk-register", help="CEO blind-spot register: obligations ranked by blast-radius x ungroundedness")
    risk.add_argument("--vertical", default="food_manufacturing")
    risk.add_argument("--evidence-file")
    risk.add_argument("--as-of", type=float, default=None)
    risk.add_argument("--top", type=int, default=3, help="how many high-risk controls escalate to the CEO")
    risk.add_argument("--org-chart", help="owner mapping: JSON {role: person} (조직도 입력)")
    risk.add_argument("--assign", help="owner mapping: JSON {contract_id|tag: person} (수동 지정)")
    risk.add_argument("--llm-owners", action="store_true", help="owner mapping: infer via Claude (LLM 추론)")
    risk.add_argument("--org-desc", help="org description passed to --llm-owners")
    risk.add_argument("--by-owner", action="store_true", help="route the register into per-owner buckets")
    risk.set_defaults(func=cmd_risk_register)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
