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

from .ir import (
    CATASTROPHIC,
    MODERATE,
    SEVERE,
    Contract,
    ContractGraph,
    NodeKind,
    Provenance,
)


@dataclass
class Spec:
    """A template node: an entailment sub-tree, before instantiation into the IR."""

    key: str
    label: str
    kind: NodeKind
    grounding_tags: list[str] = field(default_factory=list)
    requires: list["Spec"] = field(default_factory=list)
    freshness: float | None = None  # max age before a data grounding decays (None = never)
    severity: float = 0.25  # blast-radius (0..1); obligations set high, controls inherit
    owner_role: str = ""    # functional role that owns this control (정비/품질/구매/…)
    exposure: list[str] = field(default_factory=list)     # consequence classes (obligation roots set; controls inherit)
    regulations: list[str] = field(default_factory=list)  # legal detail within 법규 exposure (obligation roots set; inherit)


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
    obligations: dict[str, KpiTemplate] = field(default_factory=dict)  # what the company is accountable for

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
                severity=spec.severity,
                owner_role=spec.owner_role,
                exposure=list(spec.exposure),
                regulations=list(spec.regulations),
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


# --- Cross-cutting obligations (apply to almost any company; shared across verticals) --- #

_PRIVACY = KpiTemplate(
    key="privacy",
    label="개인정보 보호 / personal-data protection",
    aliases=["개인정보", "privacy", "프라이버시"],
    root=Spec(
        key="privacy",
        label="개인정보 보호 통제",
        kind=NodeKind.OBLIGATION,
        severity=SEVERE,
        exposure=["법규", "브랜드·여론"],
        regulations=["개인정보보호법"],
        requires=[
            Spec("privacy_policy_posted", "개인정보 처리방침 게시·최신화", NodeKind.RECORD, grounding_tags=["privacy_policy"], owner_role="정보보호"),
            Spec("consent_record", "수집·이용 동의 기록", NodeKind.RECORD, grounding_tags=["consent_log"], owner_role="정보보호"),
            Spec("access_log", "개인정보 접근권한·접근 기록", NodeKind.RECORD, grounding_tags=["access_log"], owner_role="IT"),
            Spec("disposal_record", "보유기간 경과 파기 기록", NodeKind.RECORD, grounding_tags=["disposal_log"], owner_role="정보보호"),
        ],
    ),
)

_ENVIRONMENT = KpiTemplate(
    key="environment",
    label="환경 통제 / environmental compliance",
    aliases=["환경", "폐수", "화학물질", "environment"],
    root=Spec(
        key="environment",
        label="환경·유해물질 통제",
        kind=NodeKind.OBLIGATION,
        severity=SEVERE,
        exposure=["법규", "노무·ESG", "브랜드·여론"],
        regulations=["화학물질관리법", "물환경보전법"],
        requires=[
            Spec("haz_chem_record", "유해화학물질 취급·보관 기록", NodeKind.RECORD, grounding_tags=["haz_chem_log"], owner_role="환경안전"),
            Spec("wastewater_measure", "폐수 배출 수질 측정 기록", NodeKind.RECORD, grounding_tags=["wastewater_log"], owner_role="환경안전"),
            Spec("msds_management", "MSDS 비치·갱신 기록", NodeKind.RECORD, grounding_tags=["msds"], owner_role="환경안전"),
        ],
    ),
)

_FINANCIAL_CONTROL = KpiTemplate(
    key="financial_control",
    label="재무 내부통제 / financial internal control",
    aliases=["재무통제", "내부통제", "financial control"],
    root=Spec(
        key="financial_control",
        label="재무 내부통제",
        kind=NodeKind.OBLIGATION,
        severity=SEVERE,
        exposure=["법규", "재무"],
        regulations=["주식회사 등의 외부감사에 관한 법률", "상법(내부통제)"],
        requires=[
            Spec("fund_approval", "자금 집행 승인 통제 기록", NodeKind.RECORD, grounding_tags=["approval_log"], owner_role="재무"),
            Spec("tax_invoice_recon", "세금계산서 대사 기록", NodeKind.RECORD, grounding_tags=["tax_recon"], owner_role="재무"),
            Spec("inventory_count", "재고 실사 기록", NodeKind.RECORD, grounding_tags=["stock_count"], owner_role="재무"),
        ],
    ),
)


# --- Obligations: what the company is *accountable* for (the CEO's liability surface) --- #
# The apex is high-severity; controls inherit that blast radius. These exist whether or not
# a manager asked — they are the risks that arrive at the CEO invisibly until they detonate.

_INJ_PRODUCT_LIABILITY = KpiTemplate(
    key="product_liability",
    label="제조물 책임 / product liability (불량 유출·리콜)",
    aliases=["제조물책임", "리콜", "product liability", "recall"],
    root=Spec(
        key="product_liability",
        label="제조물 책임 통제 (유출·추적·인증)",
        kind=NodeKind.OBLIGATION,
        severity=SEVERE,
        exposure=["법규", "안전·생명", "브랜드·여론"],
        regulations=["제조물책임법"],
        requires=[
            Spec("defect_escape_control", "불량 유출 방지 — 검사 기록 존재", NodeKind.RECORD, grounding_tags=["inspection_log"], owner_role="품질"),
            Spec("material_cert", "원료 물성·유해물질 인증 기록", NodeKind.RECORD, grounding_tags=["material_cert"], owner_role="구매"),
            Spec("recall_lot_link", "리콜 시 로트 역추적 연결", NodeKind.RECORD, grounding_tags=["lot_link"], owner_role="생산"),
        ],
    ),
)

_INJ_WORKER_SAFETY = KpiTemplate(
    key="worker_safety",
    label="작업자 안전 / worker safety (설비·중대재해)",
    aliases=["안전", "중대재해", "safety", "loto"],
    root=Spec(
        key="worker_safety",
        label="작업자 안전 통제",
        kind=NodeKind.OBLIGATION,
        severity=CATASTROPHIC,
        exposure=["안전·생명", "법규", "노무·ESG"],
        regulations=["중대재해처벌법", "산업안전보건법"],
        requires=[
            Spec("loto_record", "설비 정비 시 LOTO(잠금·표찰) 기록", NodeKind.RECORD, grounding_tags=["loto_log"], owner_role="정비"),
            Spec("guard_check", "방호장치 점검 판정 — 사람 루프", NodeKind.JUDGMENT, grounding_tags=["guard_check"], owner_role="안전"),
        ],
    ),
)

INJECTION_MOLDING = VerticalTemplate(
    name="injection_molding",
    kpis={t.key: t for t in (_DEFECT_RATE, _DOWNTIME, _ON_TIME)},
    obligations={t.key: t for t in (_INJ_PRODUCT_LIABILITY, _INJ_WORKER_SAFETY, _ENVIRONMENT, _PRIVACY, _FINANCIAL_CONTROL)},
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


_FOOD_CONSUMER_SAFETY = KpiTemplate(
    key="consumer_safety",
    label="소비자 안전 / consumer safety (이물·알레르겐·공급사·리콜)",
    aliases=["소비자안전", "이물", "알레르겐", "consumer safety", "recall"],
    root=Spec(
        key="consumer_safety",
        label="소비자 안전 통제 — 파장: 리콜·브랜드·규제",
        kind=NodeKind.OBLIGATION,
        severity=CATASTROPHIC,
        exposure=["안전·생명", "브랜드·여론", "법규"],
        regulations=["식품위생법", "식품 등의 표시·광고에 관한 법률", "제조물책임법"],
        requires=[
            Spec("foreign_body_control", "금속검출기/이물 검사 기록", NodeKind.RECORD, grounding_tags=["metal_detector_log"], owner_role="품질"),
            Spec("allergen_labeling", "알레르겐 표시 검증 기록", NodeKind.RECORD, grounding_tags=["allergen_label"], owner_role="품질"),
            Spec("supplier_material_cert", "공급사 소재 안전 인증(예: 판촉물 유해물질)", NodeKind.RECORD, grounding_tags=["supplier_cert"], owner_role="구매"),
            Spec("recall_traceability", "리콜 시 배합 로트 역추적 — 흔히 머릿속(은닉)", NodeKind.RECORD, grounding_tags=["batch_link"], owner_role="생산"),
        ],
    ),
)

FOOD_MANUFACTURING = VerticalTemplate(
    name="food_manufacturing",
    kpis={t.key: t for t in (_SANITATION, _TRACEABILITY)},
    obligations={t.key: t for t in (_FOOD_CONSUMER_SAFETY, _ENVIRONMENT, _PRIVACY, _FINANCIAL_CONTROL)},
)


# --------------------------------------------------------------------------- #
# Third vertical: foodservice / franchise (외식·프랜차이즈) — closest to the Starbucks case
# --------------------------------------------------------------------------- #

_FS_STORE_HYGIENE = KpiTemplate(
    key="store_hygiene",
    label="매장 위생 점검 준수율 / store hygiene",
    aliases=["위생", "매장위생", "hygiene"],
    root=Spec(
        key="store_hygiene",
        label="매장 위생 준수율 = 준수 점검 / 전체 점검",
        kind=NodeKind.KPI,
        requires=[
            Spec("hygiene_check_record", "매장 위생 점검 체크리스트 기록", NodeKind.RECORD, grounding_tags=["store_hygiene_log"], owner_role="매장운영"),
        ],
    ),
)

_FS_CONSUMER_SAFETY = KpiTemplate(
    key="consumer_safety",
    label="소비자 안전 / consumer safety (위생·알레르기·원산지)",
    aliases=["소비자안전", "알레르기", "원산지", "consumer safety"],
    root=Spec(
        key="consumer_safety",
        label="매장 소비자 안전 통제",
        kind=NodeKind.OBLIGATION,
        severity=CATASTROPHIC,
        exposure=["안전·생명", "브랜드·여론", "법규"],
        regulations=["식품위생법", "식품 등의 표시·광고에 관한 법률", "농수산물의 원산지 표시 등에 관한 법률"],
        requires=[
            Spec("store_hygiene_record", "매장 위생 점검 기록", NodeKind.RECORD, grounding_tags=["store_hygiene_log"], owner_role="매장운영"),
            Spec("allergen_notice", "알레르기 유발물질 고지", NodeKind.RECORD, grounding_tags=["allergen_label"], owner_role="매장운영"),
            Spec("origin_labeling", "원산지 표시 기록", NodeKind.RECORD, grounding_tags=["origin_label"], owner_role="구매"),
        ],
    ),
)

_FS_PROMO_LOAD = KpiTemplate(
    key="promo_operational_load",
    label="프로모션 운영 부하 / promo operational load (스타벅스 리유저블컵데이형)",
    aliases=["프로모션", "판촉", "이벤트", "promo"],
    root=Spec(
        key="promo_operational_load",
        label="판촉 이벤트가 매장을 마비시키지 않게 하는 통제",
        kind=NodeKind.OBLIGATION,
        severity=SEVERE,
        exposure=["노무·ESG", "브랜드·여론", "정치"],  # 법을 어긴 게 아니라 대중·노무 정서가 폭발한 축
        regulations=["근로기준법"],
        requires=[
            Spec("demand_forecast", "프로모션 수요 예측 기록", NodeKind.RECORD, grounding_tags=["promo_forecast"], owner_role="마케팅"),
            Spec("staffing_record", "프로모션일 매장 인력 배치 기록", NodeKind.RECORD, grounding_tags=["staffing_log"], owner_role="매장운영"),
            Spec("load_threshold_alarm", "매장 부하 임계 초과 알람 — 판단 개입", NodeKind.JUDGMENT, grounding_tags=["load_alarm"], owner_role="매장운영"),
        ],
    ),
)

_FS_LABOR_SAFETY = KpiTemplate(
    key="labor_safety",
    label="노무·안전 / labor & safety",
    aliases=["노무", "근로시간", "안전교육", "labor"],
    root=Spec(
        key="labor_safety",
        label="노무·안전 통제",
        kind=NodeKind.OBLIGATION,
        severity=CATASTROPHIC,
        exposure=["안전·생명", "노무·ESG", "법규"],
        regulations=["근로기준법", "산업안전보건법", "중대재해처벌법"],
        requires=[
            Spec("work_hours_record", "근로시간 기록", NodeKind.RECORD, grounding_tags=["work_hours"], owner_role="인사"),
            Spec("safety_training_record", "안전보건교육 이수 기록", NodeKind.RECORD, grounding_tags=["safety_training"], owner_role="인사"),
        ],
    ),
)

FOODSERVICE_FRANCHISE = VerticalTemplate(
    name="foodservice_franchise",
    kpis={t.key: t for t in (_FS_STORE_HYGIENE,)},
    obligations={t.key: t for t in (_FS_CONSUMER_SAFETY, _FS_PROMO_LOAD, _FS_LABOR_SAFETY, _PRIVACY, _FINANCIAL_CONTROL)},
)


VERTICALS: dict[str, VerticalTemplate] = {
    INJECTION_MOLDING.name: INJECTION_MOLDING,
    FOOD_MANUFACTURING.name: FOOD_MANUFACTURING,
    FOODSERVICE_FRANCHISE.name: FOODSERVICE_FRANCHISE,
}
