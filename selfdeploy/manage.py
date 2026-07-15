"""The CEO management loop: propose → select → cascade → manage.

Repositions the whole thing from a *defensive/CYA risk register* into a
*CEO-centric management tool*. Risk is one lens, not the identity: the surface
unifies the performance lens (P1~P4 categories: 수익성/비용/성장/운영) and the
risk lens (C1~C8 obligation categories) into one "what needs management" list.
The CEO SELECTS what to steer — with a "왜 지금" rationale per item — it
CASCADES to owners as help (not blame), and its status is framed in management
terms (사각지대/진행중/관리중) and tracked over time (state.py).

  ① 제안  management_surface() — performance + risk items, by category
  ② 선택  select() + rationale() — the CEO chooses, with grounds
  ③ 케스케이딩  cascade()      — routed to the role that owns it
  ④ 관리  state.track/snapshot/progress — 사각지대 → 관리중 as a trajectory
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .categories import RISK_CATEGORIES, kpi_category
from .collectors import DEFAULT_CATALOG
from .decompose import build_graph, build_kpi_graph, build_obligation_graph
from .grounding import Evidence, Grade, ground
from .owners import Resolver, assign_owners, template_resolver
from .risk import risk_register
from .templates import VerticalTemplate

# management-framed status (steering language, not exposure/defense language)
STATUS = {
    Grade.VERIFIED: "관리중 (확보)",
    Grade.JUDGMENT: "사람이 관리중",
    Grade.UNVERIFIED: "진행중 (미확정)",
    Grade.RED: "사각지대 (미착수)",
}

_OBL_TO_CATEGORY: dict[str, tuple[str, str]] = {}
for _cat in RISK_CATEGORIES:
    for _ob in _cat.obligations:
        _OBL_TO_CATEGORY[_ob] = (_cat.code, _cat.name)

_CASES_BY_CODE = {c.code: c.cases for c in RISK_CATEGORIES}


def _template_key(contract_id: str) -> str:
    parts = contract_id.split(":")
    return parts[1] if len(parts) >= 2 else ""


@dataclass
class ManagedItem:
    contract_id: str
    label: str
    category: str            # "C4 오너·임원 품행" / "P1 수익성"
    category_code: str       # "C4" | "P1" | ...
    status: str
    owner: Optional[str]
    weight: float            # risk (obligation) or ungroundedness proxy (kpi)
    exposure: list[str] = field(default_factory=list)
    human_only: Optional[bool] = None  # closeable by sensing/systems, or people-gate only


def _kpi_human_only(tags: list[str]) -> bool:
    return not any(set(c.covers) & set(tags) for c in DEFAULT_CATALOG)


def management_surface(
    vertical: VerticalTemplate,
    evidence: Evidence,
    requirement: str = "",
    mapper=None,
    resolver: Optional[Resolver] = None,
) -> list[ManagedItem]:
    """① 제안 — the unified surface of what needs management: performance + risk.

    With a requirement, the performance lens narrows to what the CEO voiced;
    without one, the full performance grammar is proposed (the tool knows what a
    company of this type should be steering, mirroring the obligation surface).
    """
    resolver = resolver or template_resolver()
    items: list[ManagedItem] = []

    # risk lens — obligation categories
    g = assign_owners(ground(build_obligation_graph(vertical), evidence), resolver)
    for it in risk_register(g):
        code, name = _OBL_TO_CATEGORY.get(_template_key(it.contract_id), ("C?", "기타 리스크"))
        items.append(ManagedItem(
            it.contract_id, it.label, f"{code} {name}", code,
            STATUS[it.grade], it.owner, it.risk, it.exposure, it.human_only,
        ))

    # performance lens — voiced requirement, or the full KPI grammar
    if requirement:
        gk = build_graph(requirement, vertical, mapper)
    else:
        gk = build_kpi_graph(vertical)
    assign_owners(ground(gk, evidence), resolver)
    for node in gk.leaves():
        grade = node.grade or Grade.RED
        if grade == Grade.VERIFIED:
            continue
        code, name = kpi_category(_template_key(node.id))
        weight = {Grade.RED: 1.0, Grade.UNVERIFIED: 0.6, Grade.JUDGMENT: 0.3}[grade]
        items.append(ManagedItem(
            node.id, node.label, f"{code} {name}", code,
            STATUS[grade], node.owner, weight, [], _kpi_human_only(node.grounding_tags),
        ))

    items.sort(key=lambda i: (-i.weight, i.category_code, i.contract_id))
    return items


def select(surface: list[ManagedItem], codes: set[str] | None = None, top: int | None = None) -> list[ManagedItem]:
    """② 선택 — the CEO chooses what to steer (by category, or the top-weighted few)."""
    picked = [i for i in surface if not codes or i.category_code in codes]
    if top is not None:
        picked = picked[:top]
    return picked


def rationale(item: ManagedItem, stalled_reviews: int = 0) -> list[str]:
    """'왜 지금' — the grounds a CEO sees next to each candidate: cases, blast
    radius, exposure, cost-to-start, and (when tracked) stagnation."""
    reasons: list[str] = []
    cases = _CASES_BY_CODE.get(item.category_code, [])
    if cases:
        shown = ", ".join(f"{c.name}({c.year})" for c in cases[:2])
        more = f" 외 {len(cases) - 2}건" if len(cases) > 2 else ""
        reasons.append(f"실제 낙마 사례: {shown}{more}")
    if item.weight >= 0.9:
        reasons.append(f"파장 치명적({item.weight:.2f}) — 터지면 대표가 직접 책임지는 급")
    elif item.weight >= 0.7:
        reasons.append(f"파장 심각({item.weight:.2f})")
    if item.exposure:
        reasons.append("노출: " + "/".join(item.exposure))
    if item.human_only is False:
        reasons.append("센싱·기존 시스템으로 착지 가능 — 착수 비용 낮음(빠른 승리)")
    elif item.human_only:
        reasons.append("사람 게이트 필요 — 기록·제도 신설(인터뷰 게이트로 시작)")
    if stalled_reviews >= 2:
        reasons.append(f"⚠ {stalled_reviews}회 연속 정체 — 후속 개입 필요")
    elif item.status.startswith("사각지대"):
        reasons.append("현재 완전 미착수 — 첫 조치가 즉시 진척으로 기록됨")
    return reasons


def cascade(selected: list[ManagedItem]) -> dict[str, list[ManagedItem]]:
    """③ 케스케이딩 — route the selected initiatives to their owners (help, not blame)."""
    buckets: dict[str, list[ManagedItem]] = {}
    for it in selected:
        buckets.setdefault(it.owner or "미지정", []).append(it)
    return buckets


def status_summary(items: list[ManagedItem]) -> dict[str, int]:
    """④ 관리 — how the selected initiatives sit across management states."""
    out: dict[str, int] = {}
    for it in items:
        out[it.status] = out.get(it.status, 0) + 1
    return out


def current_statuses(
    vertical: VerticalTemplate,
    evidence: Evidence,
    resolver: Optional[Resolver] = None,
) -> dict[str, str]:
    """Every leaf's current management status — VERIFIED included, because a
    tracked initiative graduating to 관리중 is exactly what snapshots must record."""
    resolver = resolver or template_resolver()
    statuses: dict[str, str] = {}
    for graph in (build_obligation_graph(vertical), build_kpi_graph(vertical)):
        assign_owners(ground(graph, evidence), resolver)
        for node in graph.leaves():
            statuses[node.id] = STATUS[node.grade or Grade.RED]
    return statuses
