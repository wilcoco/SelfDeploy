"""CEO-risk category taxonomy, derived from ~30 years of CEO-ousting cases.

Grounding the obligation model in what actually removed CEOs — not an a-priori
compliance checklist. Each category lists representative cases and the obligation
templates that now cover it. See docs/CEO-RISK-CASES.md for the full catalog and
sources. The lesson of the survey: Korean CEOs fall to *personal conduct / gapjil*,
*partner abuse*, and *consumer deception* far more than to the operational-safety
risks a manufacturing compliance view emphasizes.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Case:
    name: str
    year: str
    who_fell: str


@dataclass
class RiskCategory:
    code: str
    name: str
    exposure: list[str]
    cases: list[Case] = field(default_factory=list)
    obligations: list[str] = field(default_factory=list)  # obligation keys covering it


RISK_CATEGORIES: list[RiskCategory] = [
    RiskCategory(
        "C1", "안전·품질 재해·리콜", ["안전·생명", "법규", "브랜드·여론"],
        [Case("보잉 737 MAX 도어플러그", "2024", "Dave Calhoun CEO 사임"),
         Case("펠로톤 트레드밀 사망·리콜 지연", "2021", "John Foley CEO 교체")],
        ["product_liability", "consumer_safety", "worker_safety"],
    ),
    RiskCategory(
        "C2", "금융·회계 부정·횡령·세탁", ["법규", "재무", "브랜드·여론"],
        [Case("닛산 카를로스 곤 보상 미신고", "2018", "Carlos Ghosn 축출"),
         Case("단스케방크 자금세탁", "2018", "Thomas Borgen CEO 사임"),
         Case("대표이사 횡령(다수)", "상시", "대표 형사·사임")],
        ["financial_control"],
    ),
    RiskCategory(
        "C3", "소비자 기만·영업 부정", ["법규", "브랜드·여론", "재무"],
        [Case("웰스파고 유령계좌", "2016", "John Stumpf CEO 사임"),
         Case("남양유업 불가리스 코로나 효과 허위", "2021", "홍원식 회장 사퇴·매각")],
        ["consumer_honesty"],
    ),
    RiskCategory(
        "C4", "오너·임원 개인 품행(갑질·비위)", ["윤리·품행", "브랜드·여론", "법규", "노무·ESG"],
        [Case("대한항공 땅콩회항", "2014", "조현아 부사장 사퇴"),
         Case("한화 김승연 보복폭행", "2007", "회장 유죄"),
         Case("미스터피자 정우현 갑질", "2017", "회장 경영 퇴진·유죄"),
         Case("맥도날드 Easterbrook 부적절 관계", "2019", "CEO 해임"),
         Case("올림푸스 Kaufmann 약물", "2024", "CEO 사임"),
         Case("WWE McMahon 성비위 무마금", "2022", "CEO 사임")],
        ["exec_conduct"],
    ),
    RiskCategory(
        "C5", "파트너·협력사 갑질(대리점·가맹점)", ["법규", "브랜드·여론", "노무·ESG"],
        [Case("남양유업 대리점 밀어내기", "2013", "불매 10년→오너경영 종료"),
         Case("미스터피자 가맹점 갑질", "2017", "회장 퇴진")],
        ["partner_fairness"],
    ),
    RiskCategory(
        "C6", "노무·조직문화·성비위", ["노무·ESG", "윤리·품행", "브랜드·여론", "법규"],
        [Case("우버 독성문화·성희롱 대응", "2017", "Travis Kalanick CEO 사임"),
         Case("WWE 성비위", "2022", "McMahon 사임")],
        ["workplace_culture", "labor_safety"],
    ),
    RiskCategory(
        "C7", "홍보·마케팅 정서 충돌", ["역사·사회", "브랜드·여론", "정치"],
        [Case("스타벅스 탱크데이(5·18/박종철 연상)", "2026", "손정현 대표 해임")],
        ["brand_sensitivity"],
    ),
    RiskCategory(
        "C8", "규제·컴플라이언스(환경·개인정보 등)", ["법규", "브랜드·여론"],
        [Case("각종 환경·개인정보·공정거래 규제 위반", "상시", "과징금·대표 문책")],
        ["environment", "privacy", "financial_control"],
    ),
]


# --------------------------------------------------------------------------- #
# Performance categories — the other half of a management tool.
# Risk tells the CEO what can end them; performance tells them what they're
# actually hired to grow. Both sit on the same propose→select→cascade→manage loop.
# --------------------------------------------------------------------------- #

@dataclass
class PerfCategory:
    code: str
    name: str
    kpis: list[str] = field(default_factory=list)  # KPI template keys belonging here


PERF_CATEGORIES: list[PerfCategory] = [
    PerfCategory("P1", "수익성 (마진·수익율)", ["profitability"]),
    PerfCategory("P2", "비용 효율 (원가·손실)", ["cost_visibility"]),
    PerfCategory("P3", "성장 (매출·고객·수주)", ["sales_growth"]),
    PerfCategory("P4", "운영 효율 (품질·가동·납기·위생)",
                 ["defect_rate", "downtime", "on_time_delivery",
                  "sanitation_compliance", "lot_traceability", "store_hygiene"]),
]

_KPI_TO_PERF: dict[str, tuple[str, str]] = {}
for _pc in PERF_CATEGORIES:
    for _k in _pc.kpis:
        _KPI_TO_PERF[_k] = (_pc.code, _pc.name)


def kpi_category(kpi_key: str) -> tuple[str, str]:
    """Which performance category a KPI template belongs to."""
    return _KPI_TO_PERF.get(kpi_key, ("P?", "기타 성과"))


def coverage(all_obligation_keys: set[str]) -> list[tuple[RiskCategory, str]]:
    """Rate each category against the obligation keys that exist across our verticals."""
    out = []
    for cat in RISK_CATEGORIES:
        have = [o for o in cat.obligations if o in all_obligation_keys]
        if not cat.obligations:
            status = "미모델"
        elif len(have) == len(cat.obligations):
            status = "✓ 커버"
        elif have:
            status = "⚠ 부분"
        else:
            status = "✗ 갭"
        out.append((cat, status))
    return out
