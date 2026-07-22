"""The primary primitive: a CEO expresses a desire → wire it, or own it.

This is the essence, distilled: the ultimate-accountability holder voices a
need (risk OR opportunity), and the system does one of three things with it:

  ① 자동 답 (answered)   — the desire grounds in existing data; report it now.
  ② 담당자 + 기한 (routed) — it can't be wired, so assign the owner who could
                            answer it and track until they do (state.py).
  ③ 미확인 (unverified)   — an answer exists but only as a claim, not data.

Everything else in the codebase (requirement matching, grounding, owner routing,
tracking) is machinery beneath this one door. `ask` is that door.

Honest boundary: this WIRES a stated desire and PROPOSES known obligations/KPIs.
It does not *generate* opportunities the CEO never imagined — that is beyond
grounding, and claiming it would be overselling.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

from .decompose import expand
from .grounding import Evidence, Grade, ground
from .owners import Resolver, assign_owners, template_resolver
from .templates import VerticalTemplate

ANSWERED = "answered"      # 자동 답 — grounded in data
ROUTED = "routed"          # 담당자 + 기한 — assigned, awaiting answer
UNVERIFIED = "unverified"  # 미확인 — claim only
ESCALATE = "escalate"      # 템플릿에 없음 — needs a new measurement grammar / direct owner


def _due(at: str, days: int) -> str:
    return (date.fromisoformat(at) + timedelta(days=days)).isoformat()


def match_desire(vertical: VerticalTemplate, text: str) -> tuple[list[str], list[str]]:
    """Deterministic desire → (KPI keys, obligation keys) by template aliases."""
    t = text.lower()
    kpis = [k for k, tmpl in vertical.kpis.items() if any(a.lower() in t for a in tmpl.aliases)]
    obls = [k for k, tmpl in vertical.obligations.items() if any(a.lower() in t for a in tmpl.aliases)]
    return kpis, obls


@dataclass
class Resolution:
    contract_id: str
    label: str
    kind: str                # ANSWERED | ROUTED | UNVERIFIED
    detail: str
    owner: Optional[str] = None
    due: Optional[str] = None


@dataclass
class AskResult:
    desire: str
    matched: list[str] = field(default_factory=list)   # matched template keys
    escalated: bool = False
    resolutions: list[Resolution] = field(default_factory=list)

    @property
    def counts(self) -> dict[str, int]:
        out = {ANSWERED: 0, ROUTED: 0, UNVERIFIED: 0}
        for r in self.resolutions:
            out[r.kind] = out.get(r.kind, 0) + 1
        return out

    @property
    def verdict(self) -> str:
        c = self.counts
        if self.escalated:
            return "욕구가 템플릿에 없음 — 담당자 직접 지정 필요"
        if c[ROUTED] == 0 and c[UNVERIFIED] == 0:
            return "지금 자동으로 답할 수 있음"
        if c[ANSWERED] == 0:
            return "지금은 답 못 함 — 담당자에게 물어 추적"
        return f"부분 답 — 자동 {c[ANSWERED]}건, 담당자 대기 {c[ROUTED] + c[UNVERIFIED]}건"


def ask(
    desire: str,
    vertical: VerticalTemplate,
    evidence: Evidence,
    at: str,
    due_days: int = 7,
    resolver: Optional[Resolver] = None,
    mapper=None,
) -> AskResult:
    """Express a desire; get it wired (auto) or owned (routed+tracked)."""
    resolver = resolver or template_resolver()
    kpis, obls = match_desire(vertical, desire)

    if mapper is not None:  # optional LLM deepening — union with keyword matches, keys stay gated
        if hasattr(mapper, "map_desire"):  # ClaudeDesireMapper: KPI + obligation routing
            mk, mo = mapper.map_desire(desire, vertical)
            kpis = list(dict.fromkeys(kpis + [k for k in mk if k in vertical.kpis]))
            obls = list(dict.fromkeys(obls + [k for k in mo if k in vertical.obligations]))
        else:  # legacy KPI-only RequirementMapper
            kpis = list(dict.fromkeys(kpis + [k for k in mapper.map(desire, vertical) if k in vertical.kpis]))

    result = AskResult(desire=desire, matched=kpis + obls)

    if not kpis and not obls:
        result.escalated = True
        result.resolutions.append(Resolution(
            "ask:unknown", desire, ROUTED,
            "이 욕구를 아는 측정 문법이 없음 — 새 템플릿 채굴 대상",
            owner="전략", due=_due(at, due_days),
        ))
        return result

    templates = [(f"kpi:{k}", vertical.kpis[k]) for k in kpis] + \
                [(f"obl:{k}", vertical.obligations[k]) for k in obls]

    for prefix, tmpl in templates:
        g = assign_owners(ground(expand(tmpl, prefix=prefix), evidence), resolver)
        for node in g.leaves():
            grade = node.grade or Grade.RED
            if grade == Grade.VERIFIED:
                result.resolutions.append(Resolution(
                    node.id, node.label, ANSWERED, node.note or "데이터로 착지"))
            elif grade == Grade.UNVERIFIED:
                result.resolutions.append(Resolution(
                    node.id, node.label, UNVERIFIED, node.note or "주장만 있음 — 데이터 미확인",
                    owner=node.owner, due=_due(at, due_days)))
            else:  # RED or unowned judgment
                result.resolutions.append(Resolution(
                    node.id, node.label, ROUTED,
                    "기존 시스템에 없음 — 담당자 지정, 답 대기",
                    owner=node.owner or "미지정", due=_due(at, due_days)))
    return result
