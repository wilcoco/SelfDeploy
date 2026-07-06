"""The deterministic grounding gate.

This is where the executive's requirement stops being a slide and hits reality.
Given the ought-graph (from the template) and the company's actual evidence, we
compute a grade for every contract. Nondeterminism (the LLM decompose step) is
upstream; this gate is fully deterministic — same inputs, same grades.

Rules per contract:
  * matched by a DATA signal   -> VERIFIED   (provenance LOG_DERIVED)
  * matched only by a CLAIM     -> UNVERIFIED (provenance DECLARED)  — the rubber-stamp
  * no evidence, is a leaf      -> RED        (provenance MISSING)    — the worklist
  * judgment node, has an owner -> JUDGMENT   (acknowledged human-in-loop)
  * judgment node, no owner     -> RED        (an unowned human call is still a gap)
  * internal node               -> worst() of its own direct grade and its children

The honest definition of "done": a KPI is VERIFIED only if *every* entailed
record grounds in a real event. That is the whole difference from a BI tool.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .ir import Contract, ContractGraph, Grade, NodeKind, Provenance, worst


@dataclass
class Signal:
    """One thing the company actually has."""

    id: str
    kind: str                 # "data" (recorded/queryable) or "claim" (stated only, e.g. in a manual)
    tags: list[str] = field(default_factory=list)
    description: str = ""


@dataclass
class Evidence:
    """The company's real state: what it records, what it merely claims, who owns judgment."""

    signals: list[Signal] = field(default_factory=list)
    judgment_owners: dict[str, str] = field(default_factory=dict)  # grounding_tag -> owner name

    def match(self, tags: list[str]) -> tuple[str | None, Signal | None]:
        """Return ('data'|'claim'|None, signal) for the strongest signal sharing a tag."""
        best_kind: str | None = None
        best_signal: Signal | None = None
        for sig in self.signals:
            if set(sig.tags) & set(tags):
                if sig.kind == "data":
                    return "data", sig       # data is strongest; short-circuit
                if best_kind is None:
                    best_kind, best_signal = "claim", sig
        return best_kind, best_signal

    def owner_for(self, tags: list[str]) -> str | None:
        for tag in tags:
            if tag in self.judgment_owners:
                return self.judgment_owners[tag]
        return None


def _direct_grade(node: Contract, evidence: Evidence) -> Grade | None:
    """Grade from this node's *own* evidence, ignoring children. None if it has no tags."""
    if node.kind == NodeKind.JUDGMENT:
        owner = evidence.owner_for(node.grounding_tags)
        if owner:
            node.owner = owner
            node.provenance = Provenance.DECLARED
            node.note = f"사람 판단 — 담당: {owner}"
            return Grade.JUDGMENT
        node.provenance = Provenance.MISSING
        node.note = "사람 판단인데 담당자 미지정 — 여전히 간극"
        return Grade.RED

    if not node.grounding_tags:
        return None  # structural internal node: grade comes from children only

    kind, sig = evidence.match(node.grounding_tags)
    if kind == "data":
        node.provenance = Provenance.LOG_DERIVED
        node.note = f"데이터로 착지: {sig.id}"
        return Grade.VERIFIED
    if kind == "claim":
        node.provenance = Provenance.DECLARED
        node.note = f"주장만 있음(미검증): {sig.id}"
        return Grade.UNVERIFIED
    # leaf with no evidence -> red cell
    node.provenance = Provenance.MISSING
    node.note = "증거 없음 — 빨간 칸"
    return Grade.RED


def ground(graph: ContractGraph, evidence: Evidence) -> ContractGraph:
    """Compute and store a grade on every contract. Returns the same graph."""

    def compute(node_id: str) -> Grade:
        node = graph.get(node_id)
        if node.kind == NodeKind.JUDGMENT:
            grade = _direct_grade(node, evidence)
            node.grade = grade
            return grade

        child_grades = [compute(cid) for cid in node.requires]
        direct = _direct_grade(node, evidence)

        candidates = list(child_grades)
        if direct is not None:
            candidates.append(direct)
        if not candidates:
            node.grade = Grade.RED
            node.provenance = Provenance.MISSING
            node.note = "착지할 것이 없음"
        else:
            node.grade = worst(candidates)
            if not node.note:
                node.note = f"하위 계약 중 최악: {node.grade.value}"
        return node.grade

    compute(graph.root_id)
    return graph


@dataclass
class Metrics:
    total: int
    verified: int
    unverified: int
    red: int
    judgment: int

    @property
    def red_density(self) -> float:
        """The product's life-or-death metric: fraction of contracts that are red cells."""
        return self.red / self.total if self.total else 0.0


def metrics(graph: ContractGraph) -> Metrics:
    counts = {g: 0 for g in Grade}
    for node in graph.iter_nodes():
        if node.grade is not None:
            counts[node.grade] += 1
    total = sum(counts.values())
    return Metrics(
        total=total,
        verified=counts[Grade.VERIFIED],
        unverified=counts[Grade.UNVERIFIED],
        red=counts[Grade.RED],
        judgment=counts[Grade.JUDGMENT],
    )
