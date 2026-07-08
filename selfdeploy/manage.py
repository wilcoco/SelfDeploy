"""The CEO management loop: propose → select → cascade → manage.

Repositions the whole thing from a *defensive/CYA risk register* into a
*CEO-centric management tool*. Risk is one lens, not the identity: the surface
unifies the performance lens (a manager's KPI requirements) and the risk lens
(the obligation categories) into one "what needs management" list. The CEO
SELECTS what to steer, it CASCADES to owners as help (not blame), and its status
is framed in management terms (확보/진행중/사각지대), not exposure.

  ① 제안  management_surface() — performance + risk items, by category
  ② 선택  select()            — the CEO chooses what to steer
  ③ 케스케이딩  owners         — routed to the role that owns it
  ④ 관리  status              — tracked as it moves 사각지대 → 관리중
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .categories import RISK_CATEGORIES
from .decompose import build_graph, build_obligation_graph
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


def _obligation_key(contract_id: str) -> str:
    return contract_id.split(":")[1] if contract_id.startswith("obl:") else ""


@dataclass
class ManagedItem:
    contract_id: str
    label: str
    category: str            # "C4 오너품행" or "성과 KPI"
    category_code: str       # "C4" | "성과"
    status: str
    owner: Optional[str]
    weight: float            # risk (obligation) or 1-groundedness proxy (kpi)
    exposure: list[str] = field(default_factory=list)


def management_surface(
    vertical: VerticalTemplate,
    evidence: Evidence,
    requirement: str = "",
    mapper=None,
    resolver: Optional[Resolver] = None,
) -> list[ManagedItem]:
    """① 제안 — the unified surface of what needs management: performance + risk."""
    resolver = resolver or template_resolver()
    items: list[ManagedItem] = []

    # risk lens — obligation categories
    g = assign_owners(ground(build_obligation_graph(vertical), evidence), resolver)
    for it in risk_register(g):
        code, name = _OBL_TO_CATEGORY.get(_obligation_key(it.contract_id), ("C?", "기타"))
        items.append(ManagedItem(
            it.contract_id, it.label, f"{code} {name}", code,
            STATUS[it.grade], it.owner, it.risk, it.exposure,
        ))

    # performance lens — the manager's KPI requirement (optional)
    if requirement:
        gk = assign_owners(ground(build_graph(requirement, vertical, mapper), evidence), resolver)
        for node in gk.leaves():
            grade = node.grade or Grade.RED
            if grade == Grade.VERIFIED:
                continue
            weight = {Grade.RED: 1.0, Grade.UNVERIFIED: 0.6, Grade.JUDGMENT: 0.3}[grade]
            items.append(ManagedItem(
                node.id, node.label, "성과 KPI", "성과",
                STATUS[grade], node.owner, weight, [],
            ))

    items.sort(key=lambda i: -i.weight)
    return items


def select(surface: list[ManagedItem], codes: set[str] | None = None, top: int | None = None) -> list[ManagedItem]:
    """② 선택 — the CEO chooses what to steer (by category, or the top-weighted few)."""
    picked = [i for i in surface if not codes or i.category_code in codes]
    if top is not None:
        picked = picked[:top]
    return picked


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
