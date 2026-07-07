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


@dataclass
class RiskItem:
    contract_id: str
    label: str
    severity: float          # effective (inherited) blast radius
    grade: Grade
    risk: float              # severity × ungroundedness
    human_only: bool         # no sensing alternative — needs the interview gate


def _human_only(node, catalog: list[Collector]) -> bool:
    if node.kind == NodeKind.JUDGMENT:
        return True
    return not any(set(c.covers) & set(node.grounding_tags) for c in catalog)


def risk_register(graph: ContractGraph, catalog: list[Collector] | None = None) -> list[RiskItem]:
    """Rank every ungrounded control (leaf) by risk = blast-radius × ungroundedness."""
    catalog = DEFAULT_CATALOG if catalog is None else catalog
    eff = effective_severity(graph)
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
            )
        )
    items.sort(key=lambda i: (-i.risk, -i.severity, i.contract_id))
    return items


def escalate(register: list[RiskItem], top_n: int) -> tuple[list[RiskItem], list[RiskItem]]:
    """Attention budget: the top-N high-risk controls reach the CEO; the rest are ops' worklist."""
    return register[:top_n], register[top_n:]
