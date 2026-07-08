"""CEO blind-spot risk register: rank ungrounded controls by blast radius.

The reframe made concrete. Red-cell density is the CEO's latent liability, but
not every ungrounded cell is a risk — risk = blast-radius × ungroundedness. A
control inherits the worst consequence of any obligation it supports (ancestor
max), and its ungroundedness comes from its grade. The register ranks controls
so the CEO's scarce attention goes only to where accountability is heavy and
control is missing — the next blindside first.

Honest boundary: this surfaces risks *entailed by the company's own stated
obligations* that are silently ungrounded. It converts blindside unknown-unknowns
into a ranked known-unknown register; it does not predict novel failure modes
nobody modeled.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .collectors import DEFAULT_CATALOG, Collector
from .ir import ContractGraph, Grade, NodeKind

# How uncontrolled each grade is (0 = fully controlled, 1 = no control at all).
UNGROUNDED = {
    Grade.RED: 1.0,          # no evidence — uncontrolled
    Grade.UNVERIFIED: 0.6,   # claimed / planned, not corroborated
    Grade.JUDGMENT: 0.3,     # owned human call — soft spot, but acknowledged
    Grade.VERIFIED: 0.0,     # grounded in evidence — controlled
}


def effective_severity(graph: ContractGraph) -> dict[str, float]:
    """Each node inherits the worst blast-radius of itself and its ancestors."""
    eff: dict[str, float] = {}

    def walk(node_id: str, inherited: float) -> None:
        node = graph.get(node_id)
        s = max(node.severity, inherited)
        eff[node_id] = s
        for child in node.requires:
            walk(child, s)

    walk(graph.root_id, 0.0)
    return eff


def effective_regulations(graph: ContractGraph) -> dict[str, list[str]]:
    """A control inherits the legal basis of every obligation it supports (ancestor union)."""
    eff: dict[str, list[str]] = {}

    def walk(node_id: str, inherited: list[str]) -> None:
        node = graph.get(node_id)
        acc = list(inherited)
        for reg in node.regulations:
            if reg not in acc:
                acc.append(reg)
        eff[node_id] = acc
        for child in node.requires:
            walk(child, acc)

    walk(graph.root_id, [])
    return eff


@dataclass
class RiskItem:
    contract_id: str
    label: str
    severity: float          # effective (inherited) blast radius
    grade: Grade
    risk: float              # severity × ungroundedness
    human_only: bool         # no sensing alternative — needs the interview gate
    owner: Optional[str] = None  # resolved owner (routes the cascade)
    regulations: list[str] = None  # legal basis violated if this control is missing


def _human_only(node, catalog: list[Collector]) -> bool:
    if node.kind == NodeKind.JUDGMENT:
        return True
    return not any(set(c.covers) & set(node.grounding_tags) for c in catalog)


def risk_register(graph: ContractGraph, catalog: list[Collector] | None = None) -> list[RiskItem]:
    """Rank every ungrounded control (leaf) by risk = blast-radius × ungroundedness."""
    catalog = DEFAULT_CATALOG if catalog is None else catalog
    eff = effective_severity(graph)
    regs = effective_regulations(graph)
    items: list[RiskItem] = []
    for node in graph.iter_nodes():
        grade = node.grade if node.grade is not None else Grade.RED
        if grade == Grade.VERIFIED:
            continue
        if not node.is_leaf and node.kind != NodeKind.UNKNOWN:
            continue  # roll-ups are consequences, not controls
        sev = eff.get(node.id, node.severity)
        items.append(
            RiskItem(
                contract_id=node.id,
                label=node.label,
                severity=sev,
                grade=grade,
                risk=round(sev * UNGROUNDED[grade], 4),
                human_only=_human_only(node, catalog),
                owner=node.owner,
                regulations=regs.get(node.id, []),
            )
        )
    items.sort(key=lambda i: (-i.risk, -i.severity, i.contract_id))
    return items


def escalate(register: list[RiskItem], top_n: int) -> tuple[list[RiskItem], list[RiskItem]]:
    """Attention budget: the top-N high-risk controls reach the CEO; the rest are ops' worklist."""
    return register[:top_n], register[top_n:]


def by_regulation(register: list[RiskItem]) -> list[tuple[str, list[RiskItem]]]:
    """Roll the register up by legal basis — an item appears under each law it touches.

    Returns (regulation, items) sorted by the group's worst risk, so "which law am I
    most exposed on" reads off the top. Items with no regulation are omitted.
    """
    buckets: dict[str, list[RiskItem]] = {}
    for it in register:
        for reg in it.regulations or []:
            buckets.setdefault(reg, []).append(it)
    groups = [(reg, sorted(items, key=lambda i: -i.risk)) for reg, items in buckets.items()]
    groups.sort(key=lambda g: -max(i.risk for i in g[1]))
    return groups
