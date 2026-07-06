"""Requirement -> ought-graph decomposition.

The executive's requirement is the *apex output* we pin. This stage maps that
(possibly vague) requirement onto known KPI templates and instantiates their
entailment substructure. This is the one stage where nondeterminism (an LLM)
may enter — but it is fenced by a deterministic gate: only KPI templates that
exist in the vertical grammar can be instantiated. A requirement that maps to no
template does not get quietly dropped; it becomes an explicit RED "unknown"
contract — a Kind-B gap that says "we need to author a new template here."
"""
from __future__ import annotations

from typing import Optional, Protocol

from .ir import Contract, ContractGraph, Grade, NodeKind, Provenance
from .templates import VerticalTemplate, expand


class RequirementMapper(Protocol):
    """Pluggable requirement->KPI mapper (e.g. an LLM). Must return known KPI keys."""

    def map(self, requirement_text: str, vertical: VerticalTemplate) -> list[str]:
        ...


def build_graph(
    requirement_text: str,
    vertical: VerticalTemplate,
    mapper: Optional[RequirementMapper] = None,
) -> ContractGraph:
    """Turn a raw requirement into the full ought-graph.

    A synthetic REQUIREMENT root holds the matched KPI subtrees. Unmatched intent
    surfaces as an UNKNOWN red cell rather than disappearing.
    """
    if mapper is not None:
        matched = [k for k in mapper.map(requirement_text, vertical) if k in vertical.kpis]
    else:
        matched = vertical.match(requirement_text)

    graph = ContractGraph(root_id="req:root")
    root = Contract(
        id="req:root",
        label=f"경영자 요구사항: {requirement_text.strip()[:80]}",
        kind=NodeKind.REQUIREMENT,
        provenance=Provenance.DECLARED,
    )
    graph.add(root)

    for kpi_key in matched:
        sub = expand(vertical.kpis[kpi_key], prefix=f"kpi:{kpi_key}")
        graph.merge(sub)
        root.requires.append(sub.root_id)

    if not matched:
        unknown = Contract(
            id="req:unknown",
            label="요구를 아는 템플릿에 매핑 못 함 — 새 Kind-B 템플릿 필요",
            kind=NodeKind.UNKNOWN,
            provenance=Provenance.MISSING,
            grade=Grade.RED,
            note="이 업종 문법에 없는 요구. 템플릿 채굴 대상.",
        )
        graph.add(unknown)
        root.requires.append(unknown.id)

    return graph
