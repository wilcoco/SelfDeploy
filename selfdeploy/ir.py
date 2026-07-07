"""Canonical contract-graph IR.

A ``Contract`` is a node: something that must be true / recorded for something
upstream to hold. Edges (``requires``) are *entailment* — a parent contract
entails its children. The IR is the single source of truth; text, gap-map and
(later) code are views projected from it, never the source.

Each contract carries a *provenance* (where its truth-claim comes from) and a
*grade* (how trustworthy it is once grounded against the company's evidence).
The whole thesis in one line: a KPI is only as trustworthy as its weakest
entailed record.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterator, Optional


class NodeKind(str, Enum):
    """What role a contract plays in the entailment tree."""

    REQUIREMENT = "requirement"   # the executive's raw ask (apex)
    OBLIGATION = "obligation"     # something the company is *accountable* for (safety, brand, legal)
    KPI = "kpi"                   # a concrete, measurable target
    DEFINITION = "definition"     # what a term means (e.g. "what counts as a defect")
    EVENT = "event"               # something that must happen (e.g. inspection occurs)
    RECORD = "record"             # something that must be recorded to be measurable
    DERIVATION = "derivation"     # a computed value from records (e.g. count / total)
    JUDGMENT = "judgment"         # irreducible human call — a legal terminal, not a gap
    UNKNOWN = "unknown"           # requirement with no template — a Kind-B gap


class Provenance(str, Enum):
    """Where a contract's truth-claim comes from — graded by how much we trust it."""

    LOG_DERIVED = "log_derived"          # backed by company data — verifiable (strong)
    DECLARED = "declared"                # claimed by a human — unverified (weak)
    DOMAIN_INFERRED = "domain_inferred"  # asserted by the vertical template (weak, needs confirm)
    MISSING = "missing"                  # no evidence at all — the red cell


class Grade(str, Enum):
    """Trustworthiness of a contract after grounding. Severity orders them."""

    VERIFIED = "verified"       # grounded in a real recorded event
    JUDGMENT = "judgment"       # acknowledged human-in-the-loop terminal (owned)
    UNVERIFIED = "unverified"   # claimed or template-inferred, not corroborated
    RED = "red"                 # missing / cannot ground — the worklist

    @property
    def severity(self) -> int:
        return _SEVERITY[self]

    @property
    def symbol(self) -> str:
        return _SYMBOL[self]


_SEVERITY = {Grade.VERIFIED: 0, Grade.JUDGMENT: 1, Grade.UNVERIFIED: 2, Grade.RED: 3}
_SYMBOL = {Grade.VERIFIED: "✓", Grade.JUDGMENT: "◐", Grade.UNVERIFIED: "?", Grade.RED: "✗"}


def worst(grades: list[Grade]) -> Grade:
    """A parent is only as trustworthy as its weakest entailed child."""
    return max(grades, key=lambda g: g.severity)


# Blast-radius levels (0..1) — the consequence if a control fails.
CATASTROPHIC = 1.0   # safety/life, recall, regulatory shutdown
SEVERE = 0.75        # brand crisis, large liability
MODERATE = 0.5       # financial loss, delivery incident
MINOR = 0.25         # local inefficiency (default)


@dataclass
class Contract:
    """A node in the contract graph."""

    id: str
    label: str
    kind: NodeKind
    requires: list[str] = field(default_factory=list)   # child contract ids (entailment)
    grounding_tags: list[str] = field(default_factory=list)  # tags an evidence signal must share to ground this
    freshness: Optional[float] = None  # max age of a data grounding before it decays to UNVERIFIED (None = never stales)
    severity: float = 0.25  # blast-radius if this goes wrong (0..1); a leaf inherits the worst of its ancestors
    # Populated by the grounding pass:
    provenance: Provenance = Provenance.DOMAIN_INFERRED
    grade: Optional[Grade] = None
    owner: Optional[str] = None        # for judgment nodes: who owns the human call
    note: str = ""                     # human-readable reason for the grade

    @property
    def is_leaf(self) -> bool:
        return not self.requires


@dataclass
class ContractGraph:
    """The IR itself: a rooted DAG of contracts."""

    root_id: str
    nodes: dict[str, Contract] = field(default_factory=dict)

    def add(self, contract: Contract) -> Contract:
        self.nodes[contract.id] = contract
        return contract

    def get(self, node_id: str) -> Contract:
        return self.nodes[node_id]

    @property
    def root(self) -> Contract:
        return self.nodes[self.root_id]

    def children(self, node_id: str) -> list[Contract]:
        return [self.nodes[cid] for cid in self.nodes[node_id].requires]

    def iter_nodes(self) -> Iterator[Contract]:
        yield from self.nodes.values()

    def leaves(self) -> list[Contract]:
        return [n for n in self.nodes.values() if n.is_leaf]

    def merge(self, other: "ContractGraph") -> None:
        """Fold another graph's nodes into this one (ids must be disjoint)."""
        for node in other.iter_nodes():
            if node.id in self.nodes:
                raise ValueError(f"id collision on merge: {node.id}")
            self.nodes[node.id] = node
