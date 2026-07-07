"""Evidence auto-collection: the sensing edge (말단 센싱 대안).

Cold-start option (i), made concrete. A Collector turns some sensing modality
into `Signal`s (with tags + as_of) that feed the grounding gate. Different
collectors cover different grounding tags, so the gap map's red cells become an
*instrumentation plan*: for each red cell, which sensing alternative could close
it — and, honestly, which cells no sensor can reach (the human-judgment hidden
layer that still needs the interview gate).

The `predictive-maintenance` project (wilcoco/predictive-maintenance) is one such
edge: non-invasive CT-current / servo-torque / pressure monitoring with
drift/dropout detection. Its readings map directly onto machine-observable tags
(machine_state, downtime_log) as strong, data-backed signals — the "instrument
the machine, not the person" path. It does NOT reach inspection or disposition
records: those live in a person's head, and the planner says so.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from .grounding import Evidence, Signal
from .ir import ContractGraph, Grade, NodeKind

STRONG = "strong"  # data-backed → grounds to VERIFIED
WEAK = "weak"      # claim/plan → grounds to UNVERIFIED


@dataclass
class Collector:
    """A sensing alternative: what tags it can produce, and (optionally) how."""

    name: str
    modality: str              # machine_sensor | data_source | manual_gate | document
    covers: list[str]          # grounding tags this collector can ground
    strength: str = STRONG     # STRONG or WEAK
    reader: Optional[Callable[[], list[Signal]]] = None  # None = catalog-only (for planning)

    def collect(self) -> list[Signal]:
        return list(self.reader()) if self.reader else []


# --------------------------------------------------------------------------- #
# Concrete collectors
# --------------------------------------------------------------------------- #

def predictive_maintenance_collector(readings: list[dict], name: str = "predictive-maintenance") -> Collector:
    """Adapter for a predictive-maintenance monitor's /ingest readings.

    Each reading: {device, value|irms, ts, state?}. state == "dropout" is a stop
    event. Machine liveness grounds `machine_state`; dropouts ground `downtime_log`.
    as_of carries the latest timestamp so a stale feed decays via the freshness rule.
    """

    def reader() -> list[Signal]:
        if not readings:
            return []
        latest = max(float(r.get("ts", 0)) for r in readings)
        sigs = [
            Signal(
                id=f"pm.machine_state@{latest:g}",
                kind="data",
                tags=["machine_state"],
                as_of=latest,
                description="비침습 설비 모니터(CT전류/토크/압력) — 설비 상태",
            )
        ]
        drops = [r for r in readings if r.get("state") == "dropout"]
        if drops:
            d = max(float(r.get("ts", 0)) for r in drops)
            sigs.append(
                Signal(
                    id=f"pm.downtime@{d:g}",
                    kind="data",
                    tags=["downtime_log", "machine_state"],
                    as_of=d,
                    description="dropout(급정지) 검출 이벤트",
                )
            )
        return sigs

    return Collector(name=name, modality="machine_sensor", covers=["machine_state", "downtime_log"], reader=reader)


def data_source_collector(name: str, covers: list[str], as_of: float | None = None) -> Collector:
    """A tap on an existing system of record (ERP/MES). Produces data signals."""

    def reader() -> list[Signal]:
        return [
            Signal(id=f"{name}.{tag}", kind="data", tags=[tag], as_of=as_of, description=f"{name} 탭")
            for tag in covers
        ]

    return Collector(name=name, modality="data_source", covers=list(covers), reader=reader)


def manual_gate_collector(name: str, covers: list[str], confirmed: bool = False, as_of: float | None = None) -> Collector:
    """A worker-confirmation gate whose trace is a byproduct of unavoidable work.

    Before deployment it yields a *plan* (claim → UNVERIFIED); once live and
    producing records it yields data (→ VERIFIED).
    """
    kind = "data" if confirmed else "claim"

    def reader() -> list[Signal]:
        return [
            Signal(id=f"{name}.{tag}", kind=kind, tags=[tag], as_of=as_of,
                   description=f"작업자 게이트({'확정 기록' if confirmed else '도입 계획'})")
            for tag in covers
        ]

    return Collector(
        name=name,
        modality="manual_gate",
        covers=list(covers),
        strength=STRONG if confirmed else WEAK,
        reader=reader,
    )


def collect_all(collectors: list[Collector], base: Evidence) -> Evidence:
    """Merge every collector's signals into a copy of the base evidence."""
    signals = list(base.signals)
    for c in collectors:
        signals.extend(c.collect())
    return Evidence(signals=signals, judgment_owners=dict(base.judgment_owners))


# --------------------------------------------------------------------------- #
# The shelf of available sensing alternatives (catalog-only; no live data)
# --------------------------------------------------------------------------- #

DEFAULT_CATALOG: list[Collector] = [
    Collector("predictive-maintenance", "machine_sensor", ["machine_state", "downtime_log"], STRONG),
    Collector("ERP-tap", "data_source", ["production_count", "order_due", "shipment_log", "incoming_lot", "finished_lot"], STRONG),
    Collector("MES-disposition", "data_source", ["disposition_log"], STRONG),
    Collector("QC-scan-gate", "manual_gate", ["inspection_log"], STRONG),
    Collector("CCP-iot-logger", "machine_sensor", ["ccp_log"], STRONG),
    Collector("doc-extract(LLM)", "document", ["defect_catalog", "ccp_catalog"], WEAK),
]
# Note: batch_link and corrective_log are intentionally covered by NO collector —
# they live in a worker's head. The planner surfaces them as human-only.


@dataclass
class GapPlan:
    contract_id: str
    label: str
    tags: list[str]
    candidates: list[str] = field(default_factory=list)   # collector names that could close it
    best_strength: Optional[str] = None                   # STRONG | WEAK | None
    human_only: bool = False


def plan_sensing(graph: ContractGraph, catalog: list[Collector] = None) -> list[GapPlan]:
    """For each unclosed leaf, which sensing alternatives could close it (if any)."""
    catalog = DEFAULT_CATALOG if catalog is None else catalog
    plans: list[GapPlan] = []
    for node in graph.iter_nodes():
        if node.grade not in (Grade.RED, Grade.UNVERIFIED) or not node.is_leaf:
            continue
        if node.kind == NodeKind.JUDGMENT:
            plans.append(GapPlan(node.id, node.label, list(node.grounding_tags), [], None, human_only=True))
            continue
        matches = [c for c in catalog if set(c.covers) & set(node.grounding_tags)]
        best = None
        if any(c.strength == STRONG for c in matches):
            best = STRONG
        elif matches:
            best = WEAK
        plans.append(
            GapPlan(
                node.id,
                node.label,
                list(node.grounding_tags),
                [c.name for c in matches],
                best,
                human_only=not matches,
            )
        )
    # human-only first (deepest hidden layer), then weak, then strong
    order = {True: 0}
    plans.sort(key=lambda p: (0 if p.human_only else (1 if p.best_strength == WEAK else 2), p.contract_id))
    return plans
