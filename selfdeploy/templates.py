"""Kind-B knowledge: per-vertical *measurement grammar* (the "ought" templates).

This is the amortizable asset. A ``KpiTemplate`` says: for this KPI to be
*truthfully* measurable, these sub-contracts must be grounded. Authored once per
vertical, reused for every customer in it. The seed here is injection molding —
the founder's own domain (CAMS) is the seed template for beachhead #1.

The template is deliberately the *ought*, not an imposition: it is used only to
generate the gap-list. Every asserted contract is justified because the
executive's own stated KPI cannot be true without it (entailment, not fiat).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .ir import Contract, ContractGraph, NodeKind, Provenance


@dataclass
class Spec:
    """A template node: an entailment sub-tree, before instantiation into the IR."""

    key: str
    label: str
    kind: NodeKind
    grounding_tags: list[str] = field(default_factory=list)
    requires: list["Spec"] = field(default_factory=list)
    freshness: float | None = None  # max age before a data grounding decays (None = never)


@dataclass
class KpiTemplate:
    key: str
    label: str
    aliases: list[str]      # keywords that map a raw requirement onto this KPI
    root: Spec


@dataclass
class VerticalTemplate:
    name: str
    kpis: dict[str, KpiTemplate]

    def match(self, requirement_text: str) -> list[str]:
        """Deterministic requirement→KPI mapping by alias keywords."""
        text = requirement_text.lower()
        return [k for k, t in self.kpis.items() if any(a.lower() in text for a in t.aliases)]


def expand(kpi: KpiTemplate, prefix: str) -> ContractGraph:
    """Instantiate a template into a fresh contract graph.

    Provenance starts at DOMAIN_INFERRED for every node: it is the ought, not yet
    grounded. The grounding pass upgrades/downgrades against real evidence.
    """
    graph = ContractGraph(root_id=f"{prefix}:{kpi.root.key}")
    counter = {"n": 0}

    def walk(spec: Spec) -> str:
        counter["n"] += 1
        node_id = f"{prefix}:{spec.key}"
        child_ids = [walk(child) for child in spec.requires]
        graph.add(
            Contract(
                id=node_id,
                label=spec.label,
                kind=spec.kind,
                requires=child_ids,
                grounding_tags=list(spec.grounding_tags),
                freshness=spec.freshness,
                provenance=Provenance.DOMAIN_INFERRED,
            )
        )
        return node_id

    walk(kpi.root)
    return graph


# --------------------------------------------------------------------------- #
# Seed vertical: injection molding (사출/도장)
# --------------------------------------------------------------------------- #

_DEFECT_RATE = KpiTemplate(
    key="defect_rate",
    label="불량률 (라인·교대별) / defect rate per line·shift",
    aliases=["불량", "defect", "yield", "수율", "불량률"],
    root=Spec(
        key="defect_rate",
        label="불량률 = 불량 수 / 생산 수",
        kind=NodeKind.KPI,
        requires=[
            Spec(
                key="defect_definition",
                label="불량의 정의 (무엇을 불량으로 세는가)",
                kind=NodeKind.DEFINITION,
                grounding_tags=["defect_catalog"],
            ),
            Spec(
                key="inspection_event",
                label="검사가 실제로 수행됨 (정의된 공정에서)",
                kind=NodeKind.EVENT,  # structural: grounded by its record existing
                requires=[
                    Spec(
                        key="inspection_record",
                        label="검사 단위별 합/불 기록 (라인·교대·타임스탬프)",
                        kind=NodeKind.RECORD,
                        grounding_tags=["inspection_log"],
                    ),
                    Spec(
                        key="borderline_call",
                        label="경계 불량 판정 (감으로 판단) — 사람 루프",
                        kind=NodeKind.JUDGMENT,
                        grounding_tags=["borderline_defect"],
                    ),
                ],
            ),
            Spec(
                key="defect_count",
                label="불량 수 집계 가능",
                kind=NodeKind.DERIVATION,
                grounding_tags=["inspection_log"],
            ),
            Spec(
                key="production_denominator",
                label="라인·교대별 생산 수 (분모)",
                kind=NodeKind.RECORD,
                grounding_tags=["production_count"],
                freshness=1.0,  # 교대(shift)마다 갱신돼야 함 — 오래되면 부식
            ),
            Spec(
                key="disposition_record",
                label="불량품 처리 기록 (리워크/폐기) — 흔히 은닉층",
                kind=NodeKind.RECORD,
                grounding_tags=["disposition_log"],
            ),
        ],
    ),
)

_DOWNTIME = KpiTemplate(
    key="downtime",
    label="설비 가동중단 시간 / equipment downtime",
    aliases=["가동중단", "downtime", "정지", "가동률", "uptime", "중단"],
    root=Spec(
        key="downtime",
        label="가동중단 시간 = Σ(정지 종료 − 정지 시작)",
        kind=NodeKind.KPI,
        requires=[
            Spec(
                key="stop_event",
                label="정지 이벤트가 발생·감지됨",
                kind=NodeKind.EVENT,  # structural: grounded by its record existing
                requires=[
                    Spec(
                        key="stop_record",
                        label="정지 시작/종료 타임스탬프 기록",
                        kind=NodeKind.RECORD,
                        grounding_tags=["downtime_log", "machine_state"],
                    ),
                ],
            ),
            Spec(
                key="reason_code",
                label="정지 사유 코드 (계획/고장/자재대기) — 사람 분류",
                kind=NodeKind.JUDGMENT,
                grounding_tags=["stop_reason"],
            ),
        ],
    ),
)

_ON_TIME = KpiTemplate(
    key="on_time_delivery",
    label="납기 준수율 / on-time delivery",
    aliases=["납기", "on-time", "delivery", "출하", "리드타임", "lead time"],
    root=Spec(
        key="on_time_delivery",
        label="납기 준수율 = 정시 출하 / 전체 출하",
        kind=NodeKind.KPI,
        requires=[
            Spec(
                key="promised_date",
                label="주문별 약속 납기일 기록",
                kind=NodeKind.RECORD,
                grounding_tags=["order_due"],
            ),
            Spec(
                key="ship_event",
                label="실제 출하 이벤트 기록 (타임스탬프)",
                kind=NodeKind.RECORD,
                grounding_tags=["shipment_log"],
            ),
        ],
    ),
)


INJECTION_MOLDING = VerticalTemplate(
    name="injection_molding",
    kpis={t.key: t for t in (_DEFECT_RATE, _DOWNTIME, _ON_TIME)},
)


# --------------------------------------------------------------------------- #
# Second vertical: food manufacturing (식품가공)
#
# Proves Kind-B amortization: a different vertical is a different measurement
# grammar authored once — the IR, grounding gate, forced questions, dual-speed
# classifier, and decay are all unchanged. The hidden layer differs (CCP
# measurements and batch lot-links live in a worker's head / on paper), so the
# *same* engine surfaces a *different* set of red cells.
# --------------------------------------------------------------------------- #

_SANITATION = KpiTemplate(
    key="sanitation_compliance",
    label="위생 점검 준수율 / sanitation (HACCP) compliance",
    aliases=["위생", "점검", "haccp", "ccp", "sanitation"],
    root=Spec(
        key="sanitation_compliance",
        label="위생 준수율 = 준수 점검 / 전체 점검",
        kind=NodeKind.KPI,
        requires=[
            Spec(
                key="ccp_definition",
                label="중요관리점(CCP)과 한계기준 정의",
                kind=NodeKind.DEFINITION,
                grounding_tags=["ccp_catalog"],
            ),
            Spec(
                key="ccp_check_event",
                label="CCP 점검이 실제로 수행됨",
                kind=NodeKind.EVENT,
                requires=[
                    Spec(
                        key="ccp_record",
                        label="CCP 측정값 기록 (온도·시간, 타임스탬프)",
                        kind=NodeKind.RECORD,
                        grounding_tags=["ccp_log"],
                        freshness=1.0,  # 매 배치/교대 갱신 — 오래되면 부식
                    ),
                    Spec(
                        key="deviation_call",
                        label="한계 근처 이탈 판정 (감으로) — 사람 루프",
                        kind=NodeKind.JUDGMENT,
                        grounding_tags=["ccp_borderline"],
                    ),
                ],
            ),
            Spec(
                key="corrective_action_record",
                label="이탈 시 조치 기록 — 흔히 은닉층",
                kind=NodeKind.RECORD,
                grounding_tags=["corrective_log"],
            ),
        ],
    ),
)

_TRACEABILITY = KpiTemplate(
    key="lot_traceability",
    label="원재료 추적성 / raw-material lot traceability",
    aliases=["추적", "로트", "traceability", "이력", "lot"],
    root=Spec(
        key="lot_traceability",
        label="추적성 = 역추적 가능 로트 / 전체 로트",
        kind=NodeKind.KPI,
        requires=[
            Spec(
                key="incoming_lot",
                label="입고 원재료 로트 기록",
                kind=NodeKind.RECORD,
                grounding_tags=["incoming_lot"],
            ),
            Spec(
                key="batch_link",
                label="배합 단계 투입 로트 연결 — 흔히 작업자 머릿속(은닉층)",
                kind=NodeKind.RECORD,
                grounding_tags=["batch_link"],
            ),
            Spec(
                key="finished_lot",
                label="완제품 로트 부여·연결",
                kind=NodeKind.RECORD,
                grounding_tags=["finished_lot"],
            ),
        ],
    ),
)


FOOD_MANUFACTURING = VerticalTemplate(
    name="food_manufacturing",
    kpis={t.key: t for t in (_SANITATION, _TRACEABILITY)},
)


VERTICALS: dict[str, VerticalTemplate] = {
    INJECTION_MOLDING.name: INJECTION_MOLDING,
    FOOD_MANUFACTURING.name: FOOD_MANUFACTURING,
}
