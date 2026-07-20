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
    LLMOrgInferer,
    LLMOwnerResolver,
    assign_owners,
    bootstrap,
    by_owner,
    manual_resolver,
    org_chart_resolver,
    template_resolver,
)
from .report import html_report, risk_register_html, text_report
from .ask import ANSWERED, ESCALATE, ROUTED, UNVERIFIED, ask
from .categories import RISK_CATEGORIES, coverage
from .clearance import ACTION_TYPES, clear_action
from .manage import (
    cascade,
    current_statuses,
    management_surface,
    rationale,
    select,
    status_summary,
)
from .state import load_portfolio, progress, save_portfolio, snapshot, track
from .state import Portfolio
from .sensitivity import LLMSensitivityChecker, check_campaign
from .risk import by_exposure, by_regulation, escalate, risk_register
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

    # owner resolution — options, all fall back to the template role
    exceptions = []
    if args.llm_org:  # infer the org chart from a free-text description, then bootstrap
        roles = sorted({n.owner_role for n in graph.iter_nodes() if n.owner_role})
        org_data = LLMOrgInferer(roles, args.org_desc or "").infer()
        result = bootstrap(graph, org_data)
        resolver, exceptions = result.resolver, result.exceptions
    elif args.org:  # bootstrap: auto-infer + surface only the unmatched roles
        result = bootstrap(graph, json.loads(Path(args.org).read_text(encoding="utf-8")))
        resolver, exceptions = result.resolver, result.exceptions
    elif args.org_chart:
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

    if args.html:
        Path(args.html).write_text(risk_register_html(vertical.name, ceo, ops, args.top), encoding="utf-8")
        print(f"이사회용 1페이지 리스크 레지스터 → {args.html}", file=sys.stderr)

    def line(it):
        sens = "사람만" if it.human_only else "센싱가능"
        who = f" [{it.owner}]" if it.owner else ""
        exp = f"  ⚑ {'/'.join(it.exposure)}" if it.exposure else ""
        reg = f"  ⚖ {', '.join(it.regulations)}" if it.regulations else ""
        return f"  [risk {it.risk:.2f}] (파장 {it.severity:.2f} × {it.grade.value}){who} {_clean_line(it.label)}  — {sens}{exp}{reg}"

    print(f"대표 리스크 레지스터 — {vertical.name} 책임 표면 (파장 × 미착지 순)\n")
    if exceptions:
        print(f"⚠ 오너 확인 필요(예외) {len(exceptions)}건 — 조직도에 없는 역할, 나머지는 자동 배정됨:")
        for _cid, _label, role in exceptions:
            print(f"    · 역할 '{role}' 담당자 미확인")
        print()

    if args.by_exposure or args.by_regulation:
        ceo_ids = {it.contract_id for it in ceo}
        groups = by_exposure(register) if args.by_exposure else by_regulation(register)
        header = "노출 클래스별 롤업 (법규만이 아닌 전 노출)" if args.by_exposure else "규제별 롤업 (법규별 미착지 노출)"
        mark = "⚑" if args.by_exposure else "⚖"
        print(f"● {header}:")
        for key, items in groups:
            top = max(i.risk for i in items)
            print(f"\n  {mark} {key} — 미착지 {len(items)}건 (최고위험 {top:.2f}):")
            for it in items:
                star = "★" if it.contract_id in ceo_ids else " "
                print(f"   {star} {line(it).strip()}")
        return 0

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


def cmd_sensitivity_check(args: argparse.Namespace) -> int:
    text = args.text
    if args.text_file:
        text = Path(args.text_file).read_text(encoding="utf-8")
    if not text:
        print("provide --text or --text-file", file=sys.stderr)
        return 2
    checker = LLMSensitivityChecker() if args.llm else None
    flags = check_campaign(text, date=args.date, llm=checker)

    print(f"캠페인 사전 민감성 점검 — 출시일 {args.date or '(미정)'}")
    if not flags:
        print("  ✓ 알려진 민감 일자·문구 충돌 없음 (단, 완전성 보장 아님 — --llm 로 심화)")
        return 0
    print(f"  ✗ {len(flags)}건 충돌 — 출시 보류 권고:")
    for f in flags:
        print(f"    · [{f.kind}] '{f.matched}' — {f.reason}")
    return 1  # non-zero: this campaign should not ship as-is


def cmd_clear_action(args: argparse.Namespace) -> int:
    text = args.text or ""
    if args.text_file:
        text = Path(args.text_file).read_text(encoding="utf-8")
    passed = set(args.passed or [])
    checker = LLMSensitivityChecker() if args.llm else None
    c = clear_action(
        args.type, text=text, date=args.date, passed=passed,
        financial_weight=args.financial, llm=checker,
    )

    verdict = "✓ CLEARED — 진행 가능" if c.cleared else "✗ BLOCKED — 진행 불가(기본 차단)"
    print(f"행위 클리어런스: [{args.type}] {verdict}")
    print(f"  CEO 중요도 {c.ceo_importance:.2f}  (재무가중 {c.financial_weight:.2f} → 리스크 증폭으로 상향)")
    if c.unknown_type:
        print("  · 모델에 없는 행위 유형 — 화이트리스트는 미지의 것을 기본 차단한다")
    if c.triggered_exposure:
        print(f"  · 노출 클래스: {'/'.join(c.triggered_exposure)}")
    if c.auto_flags:
        print(f"  · 자동 민감성 플래그 {len(c.auto_flags)}건:")
        for f in c.auto_flags:
            print(f"      - [{f.kind}] '{f.matched}' — {f.reason}")
    if c.missing_clearances:
        print(f"  · 미획득 필수 클리어런스: {', '.join(c.missing_clearances)}")
    if c.cleared:
        print("  → 모든 필수 검토 통과 + 자동 플래그 없음. 통과.")
    return 0 if c.cleared else 1


def cmd_categories(args: argparse.Namespace) -> int:
    all_keys = {k for v in VERTICALS.values() for k in v.obligations}
    print("대표이사 리스크 카테고리 (30년 사례 근거 — docs/CEO-RISK-CASES.md)\n")
    for cat, status in coverage(all_keys):
        print(f"[{cat.code}] {cat.name}   {status}")
        print(f"     노출: {'/'.join(cat.exposure)}")
        for c in cat.cases:
            print(f"     · {c.name} ({c.year}) → {c.who_fell}")
        if cat.obligations:
            print(f"     의무: {', '.join(cat.obligations)}")
        print()
    return 0


def cmd_ask(args: argparse.Namespace) -> int:
    vertical = VERTICALS.get(args.vertical)
    if vertical is None:
        print(f"unknown vertical: {args.vertical}", file=sys.stderr)
        return 2
    if not args.desire:
        print("무엇이 궁금하세요? --desire \"...\"", file=sys.stderr)
        return 2
    evidence = load_evidence(Path(args.evidence_file)) if args.evidence_file else Evidence()
    resolver = None
    if args.org_chart:
        resolver = org_chart_resolver(json.loads(Path(args.org_chart).read_text(encoding="utf-8")))
    at = _review_date(args)

    result = ask(args.desire, vertical, evidence, at=at, due_days=args.due_days,
                 resolver=resolver, mapper=_mapper(args))

    print(f'욕구: "{result.desire}"')
    print(f"→ {result.verdict}\n")

    answered = [r for r in result.resolutions if r.kind == ANSWERED]
    routed = [r for r in result.resolutions if r.kind in (ROUTED, UNVERIFIED)]
    if answered:
        print("✓ 자동 답 (데이터로 착지):")
        for r in answered:
            print(f"    · {_clean_line(r.label)} — {r.detail}")
    if routed:
        print("\n⏳ 담당자에게 물음 (답 대기·추적):")
        for r in routed:
            tag = "미확인" if r.kind == UNVERIFIED else ""
            print(f"    · [{r.owner}] {_clean_line(r.label)} — 기한 {r.due} {tag}".rstrip())

    if args.track and routed:
        pf = load_portfolio(args.track) or Portfolio(vertical=vertical.name)
        items = [SimpleItem(r.contract_id, r.label, f"욕구:{result.desire[:20]}", r.owner,
                            "진행중 (미확정)" if r.kind == UNVERIFIED else "사각지대 (미착수)")
                 for r in routed]
        added = track(pf, items, at=at)
        save_portfolio(pf, args.track)
        print(f"\n(추적 시작: {added}건 → {args.track} — `progress`로 후속)")
    return 0


class SimpleItem:
    """Adapter so ask's routed resolutions can be tracked like ManagedItems."""
    def __init__(self, contract_id, label, category, owner, status):
        self.contract_id, self.label, self.category = contract_id, label, category
        self.owner, self.status = owner, status


def _review_date(args: argparse.Namespace) -> str:
    if getattr(args, "at", None):
        return args.at
    from datetime import date

    return date.today().isoformat()


def cmd_progress(args: argparse.Namespace) -> int:
    pf = load_portfolio(args.state)
    if pf is None:
        print(f"포트폴리오 없음: {args.state} — 먼저 `manage --select … --track {args.state}`", file=sys.stderr)
        return 2
    vertical = VERTICALS.get(args.vertical or pf.vertical)
    if vertical is None:
        print(f"unknown vertical: {args.vertical or pf.vertical}", file=sys.stderr)
        return 2
    evidence = load_evidence(Path(args.evidence_file)) if args.evidence_file else Evidence()
    resolver = None
    if args.org_chart:
        resolver = org_chart_resolver(json.loads(Path(args.org_chart).read_text(encoding="utf-8")))

    at = _review_date(args)
    moved = snapshot(pf, current_statuses(vertical, evidence, resolver), at=at)
    save_portfolio(pf, args.state)
    summ = progress(pf)

    print(f"④ 관리 — 리뷰 {len(pf.reviews)}회차 ({at}), 이번에 움직인 항목 {moved}건\n")
    print(f"  추적 {summ.total}건 · 개선 {summ.improved}건 · 정체(2회+) {summ.stalled}건 · 사각지대 탈출률 {summ.graduation_rate:.0%}")
    for st, n in sorted(summ.by_status.items()):
        print(f"    {st}: {n}건")
    stalled = [t for t in pf.items.values() if t.stalled_reviews >= 2]
    if stalled:
        print("\n  ⚠ 정체 — 다음 후속 개입 지점:")
        for t in stalled:
            print(f"    · [{t.category}] {_clean_line(t.label)} ({t.owner or '미지정'}) — {t.stalled_reviews}회 연속 {t.latest_status}")
    improved = [t for t in pf.items.values() if t.improved]
    if improved:
        print("\n  ▲ 개선:")
        for t in improved:
            print(f"    · [{t.category}] {_clean_line(t.label)}: {t.first_status} → {t.latest_status}")

    if args.html:
        from .report import management_dashboard_html

        Path(args.html).write_text(management_dashboard_html(vertical.name, pf, summ, at), encoding="utf-8")
        print(f"\n대표 대시보드 → {args.html}", file=sys.stderr)
    return 0


def cmd_manage(args: argparse.Namespace) -> int:
    vertical = VERTICALS.get(args.vertical)
    if vertical is None:
        print(f"unknown vertical: {args.vertical}", file=sys.stderr)
        return 2
    evidence = load_evidence(Path(args.evidence_file)) if args.evidence_file else Evidence()
    requirement = _read_requirement(args) or ""
    resolver = None
    if args.org_chart:
        resolver = org_chart_resolver(json.loads(Path(args.org_chart).read_text(encoding="utf-8")))

    surface = management_surface(vertical, evidence, requirement=requirement, mapper=_mapper(args), resolver=resolver)

    print(f"경영 관리 루프 — {vertical.name}\n")
    print("① 제안 — 관리 대상(성과 + 리스크 카테고리, 가중치순):")
    for it in surface:
        who = f" [{it.owner}]" if it.owner else ""
        print(f"  ({it.weight:.2f}) [{it.category}] {_clean_line(it.label)} — {it.status}{who}")

    codes = set(c.strip() for c in args.select.split(",")) if args.select else None
    if not codes and args.top is None:
        print("\n(선택 없음 — 대표가 --select <카테고리코드> 또는 --top N 으로 관리 대상을 고른다)")
        return 0

    picked = select(surface, codes=codes, top=args.top)
    print(f"\n② 선택 — {len(picked)}건 " + (f"(카테고리 {', '.join(sorted(codes))})" if codes else f"(상위 {args.top})"))
    if args.why:
        for it in picked:
            print(f"  · {_clean_line(it.label)}")
            for r in rationale(it):
                print(f"      ▸ {r}")

    if args.track:
        pf = load_portfolio(args.track) or Portfolio(vertical=vertical.name)
        added = track(pf, picked, at=_review_date(args))
        save_portfolio(pf, args.track)
        print(f"\n(추적 시작: 신규 {added}건 → {args.track} — `selfdeploy progress`로 후속 리뷰)")

    print("\n③ 케스케이딩 — 오너에게 배분(비난 아닌 자원·도움):")
    for owner, items in sorted(cascade(picked).items(), key=lambda kv: -max(i.weight for i in kv[1])):
        print(f"  ▸ {owner} — {len(items)}건:")
        for it in items:
            print(f"      · {_clean_line(it.label)} — {it.status}")

    print("\n④ 관리 — 상태 요약:")
    for st, n in sorted(status_summary(picked).items()):
        print(f"  {st}: {n}건")
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
    risk.add_argument("--org", help="bootstrap: auto-infer owners from org chart, confirm only exceptions")
    risk.add_argument("--org-chart", help="owner mapping: JSON {role: person} (조직도 입력)")
    risk.add_argument("--assign", help="owner mapping: JSON {contract_id|tag: person} (수동 지정)")
    risk.add_argument("--llm-owners", action="store_true", help="owner mapping: infer via Claude (LLM 추론)")
    risk.add_argument("--llm-org", action="store_true", help="infer the org chart from --org-desc, then bootstrap")
    risk.add_argument("--org-desc", help="free-text org description for --llm-owners / --llm-org")
    risk.add_argument("--by-owner", action="store_true", help="route the register into per-owner buckets")
    risk.add_argument("--by-regulation", action="store_true", help="roll the register up by legal basis")
    risk.add_argument("--by-exposure", action="store_true", help="roll up by consequence class (법규/브랜드·여론/노무·ESG/정치/…)")
    risk.add_argument("--html", help="write a board-ready one-page risk register to this path")
    risk.set_defaults(func=cmd_risk_register)

    sens = sub.add_parser("sensitivity-check", help="pre-release check: does a campaign collide with sensitive dates/phrases (탱크데이형)")
    sens.add_argument("--text", help="campaign copy / name")
    sens.add_argument("--text-file")
    sens.add_argument("--date", help="launch date (YYYY-MM-DD or MM-DD)")
    sens.add_argument("--llm", action="store_true", help="add an LLM pass for novel collisions")
    sens.set_defaults(func=cmd_sensitivity_check)

    clr = sub.add_parser("clear-action", help="default-deny gate: an action proceeds only if it PASSES its required clearances")
    clr.add_argument("--type", required=True, help=f"action type ({', '.join(ACTION_TYPES)})")
    clr.add_argument("--text", help="action content (campaign copy, statement, name)")
    clr.add_argument("--text-file")
    clr.add_argument("--date", help="launch/effective date (YYYY-MM-DD or MM-DD)")
    clr.add_argument("--passed", nargs="*", help="clearances already affirmatively passed")
    clr.add_argument("--financial", type=float, default=0.0, help="financial weight 0..1 (does NOT lower the risk floor)")
    clr.add_argument("--llm", action="store_true")
    clr.set_defaults(func=cmd_clear_action)

    cats = sub.add_parser("categories", help="CEO-risk category taxonomy grounded in 30 years of cases")
    cats.set_defaults(func=cmd_categories)

    a = sub.add_parser("ask", help="the primary door: express a desire → wire it (auto answer) or own it (assign + track)")
    a.add_argument("--desire", help="what the CEO wants to know / not miss (natural language)")
    a.add_argument("--vertical", default="foodservice_franchise")
    a.add_argument("--evidence-file")
    a.add_argument("--org-chart")
    a.add_argument("--due-days", type=int, default=7)
    a.add_argument("--at", default=None)
    a.add_argument("--track", help="portfolio JSON path — track the routed questions until answered")
    a.add_argument("--llm", action="store_true")
    a.set_defaults(func=cmd_ask)

    mng = sub.add_parser("manage", help="CEO management loop: propose -> select -> cascade -> manage")
    mng.add_argument("--vertical", default="foodservice_franchise")
    mng.add_argument("--evidence-file")
    mng.add_argument("--requirement")
    mng.add_argument("--requirement-file")
    mng.add_argument("--select", help="category codes to steer, comma-separated (e.g. C4,C5,성과)")
    mng.add_argument("--top", type=int, default=None, help="steer the top-N weighted items")
    mng.add_argument("--org-chart", help="owner mapping JSON {role: person}")
    mng.add_argument("--why", action="store_true", help="print the '왜 지금' rationale for each selected item")
    mng.add_argument("--track", help="portfolio JSON path — start tracking the selection over time")
    mng.add_argument("--at", default=None, help="review date (YYYY-MM-DD); default today")
    mng.add_argument("--llm", action="store_true")
    mng.set_defaults(func=cmd_manage)

    prog = sub.add_parser("progress", help="④ 관리: snapshot tracked initiatives against current evidence, report the trajectory")
    prog.add_argument("--state", required=True, help="portfolio JSON from manage --track")
    prog.add_argument("--vertical", default=None, help="default: the portfolio's vertical")
    prog.add_argument("--evidence-file")
    prog.add_argument("--org-chart")
    prog.add_argument("--at", default=None, help="review date (YYYY-MM-DD); default today")
    prog.add_argument("--html", help="write the CEO management dashboard to this path")
    prog.set_defaults(func=cmd_progress)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
