"""Dual-speed classifier: is a change 상시 입력 (continuous) or 재설계 (redesign)?

The living source-of-truth runs at two speeds. Adding a value/item to an existing
contract is a *fast pulse* — light gate, same model. Changing the structure (a new
branch, a new schema, a new processing path) is a *slow pulse* — heavy gate, re-run
the three checkpoints. The promotion judgment between them is decided the same way
everything else is: by type closure against the existing contracts.

The trap the discussion flagged: something that looks like continuous input but
secretly demands a new path (a new defect type that needs a new disposition route).
That shows up here as a PROMOTE verdict — partial type match — forcing a human call
rather than silently absorbing it as noise or silently triggering a full redesign.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .grounding import Signal
from .ir import ContractGraph
from .templates import VerticalTemplate

CONTINUOUS = "continuous"  # 상시 입력 — fits existing contracts, light gate
PROMOTE = "promote"        # 승급 판정 — partial fit, a human decides
REDESIGN = "redesign"      # 재설계 — no existing contract expects it, heavy gate


@dataclass
class Verdict:
    speed: str
    reason: str
    matched_tags: list[str] = field(default_factory=list)
    novel_tags: list[str] = field(default_factory=list)


def _graph_tags(graph: ContractGraph) -> set[str]:
    tags: set[str] = set()
    for node in graph.iter_nodes():
        tags.update(node.grounding_tags)
    return tags


def classify_signal(graph: ContractGraph, signal: Signal) -> Verdict:
    """Classify a newly-arriving data/claim signal by how its tags close against the graph."""
    expected = _graph_tags(graph)
    sig_tags = set(signal.tags)
    matched = sorted(sig_tags & expected)
    novel = sorted(sig_tags - expected)

    if sig_tags and not novel:
        return Verdict(
            CONTINUOUS,
            "모든 태그가 기존 컨트랙트에 들어맞음 — 값/항목 추가, 가벼운 게이트",
            matched,
            [],
        )
    if matched and novel:
        return Verdict(
            PROMOTE,
            "일부는 기존 계약에 맞지만 새 타입도 실려 있음 — 상시입력 vs 재설계 승급 판정 필요",
            matched,
            novel,
        )
    return Verdict(
        REDESIGN,
        "어느 기존 계약도 이 신호를 기대하지 않음 — 새 구조 필요, 세 체크포인트 재실행",
        [],
        novel,
    )


def _present_kpi_keys(graph: ContractGraph) -> set[str]:
    keys: set[str] = set()
    for node_id in graph.nodes:
        if node_id.startswith("kpi:"):
            keys.add(node_id.split(":")[1])
    return keys


def classify_requirement(text: str, vertical: VerticalTemplate, graph: ContractGraph) -> Verdict:
    """Classify a new manager requirement: already-modeled KPI vs a new one."""
    present = _present_kpi_keys(graph)
    matched = vertical.match(text)
    fresh = [k for k in matched if k not in present]

    if matched and not fresh:
        return Verdict(
            CONTINUOUS,
            "이미 모델에 있는 KPI를 다시 요구 — 구조 변화 없음, 가벼운 게이트",
            matched,
            [],
        )
    if fresh:
        return Verdict(
            REDESIGN,
            f"새 KPI 요구({', '.join(fresh)}) — 새 하부구조 필요, 세 체크포인트 재실행",
            [k for k in matched if k in present],
            fresh,
        )
    return Verdict(
        REDESIGN,
        "아는 KPI에 매핑 안 됨 — 새 Kind-B 템플릿 채굴(재설계)",
        [],
        [],
    )
