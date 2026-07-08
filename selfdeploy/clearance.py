"""The whitelist action gate: default-deny risk clearance for company actions.

The architectural inversion the 탱크데이 case forces. A *blacklist* (enumerate
bad campaigns/actions and block them) can never be complete — whatever isn't on
the list passes silently, which is exactly how a CEO gets blindsided. So the gate
is a *whitelist*: no action proceeds unless it has affirmatively PASSED the risk
clearances its type requires. Absence of a flag is not clearance — only an
affirmative "reviewed & cleared" is.

Two consequences, both embodied here:

  1. Default-deny. A campaign with zero sensitivity flags is still BLOCKED until
     its required review clearance is present. Silence ≠ safe.
  2. CEO-importance is amplified by risk-touch, not financial size. A cheap
     action touching 역사·사회 / 안전·생명 outranks a huge-budget action touching
     only 재무 — because a minor promo (탱크데이) ended a CEO's tenure.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .ir import EXPOSURE_WEIGHT
from .sensitivity import Flag, check_campaign


@dataclass
class ActionType:
    name: str
    label: str
    exposure: list[str]              # consequence classes this kind of action can touch
    required_clearances: list[str]   # affirmative reviews that MUST be passed to proceed
    auto_check: str = ""             # "sensitivity" runs check_campaign; "" = none


# The company's action taxonomy. Every outward/irreversible action kind is here;
# the point of a whitelist is that an action NOT covered here is itself a gap to close,
# never a silent pass.
ACTION_TYPES: dict[str, ActionType] = {
    "campaign": ActionType("campaign", "대외 캠페인·홍보", ["역사·사회", "브랜드·여론", "정치"], ["campaign_sensitivity_review"], auto_check="sensitivity"),
    "public_statement": ActionType("public_statement", "임원 대외 발언", ["역사·사회", "브랜드·여론", "정치"], ["comms_review"], auto_check="sensitivity"),
    "product_naming": ActionType("product_naming", "제품 네이밍", ["역사·사회", "브랜드·여론"], ["naming_review"], auto_check="sensitivity"),
    "promotion_event": ActionType("promotion_event", "프로모션 이벤트(운영 부하)", ["노무·ESG", "브랜드·여론"], ["load_review"]),
    "supplier_onboarding": ActionType("supplier_onboarding", "공급사 도입", ["안전·생명", "법규", "노무·ESG"], ["supplier_cert_review"]),
    "recipe_change": ActionType("recipe_change", "레시피·원료 변경", ["안전·생명", "법규"], ["allergen_haccp_review"]),
    "fund_disbursement": ActionType("fund_disbursement", "자금 집행", ["법규", "재무"], ["finance_approval"]),
}


@dataclass
class Clearance:
    action_type: str
    cleared: bool
    triggered_exposure: list[str] = field(default_factory=list)
    auto_flags: list[Flag] = field(default_factory=list)
    missing_clearances: list[str] = field(default_factory=list)
    ceo_importance: float = 0.0     # amplified by risk-touch, independent of cost
    financial_weight: float = 0.0
    unknown_type: bool = False


def _amplifier(exposure: list[str]) -> float:
    return max((EXPOSURE_WEIGHT.get(e, 0.3) for e in exposure), default=0.3)


def clear_action(
    type_name: str,
    text: str = "",
    date: Optional[str] = None,
    passed: Optional[set] = None,
    financial_weight: float = 0.0,
    llm=None,
    action_types: Optional[dict] = None,
) -> Clearance:
    """Run one action through the default-deny gate. Cleared only if it has no auto
    flags AND every required clearance has been affirmatively passed."""
    action_types = ACTION_TYPES if action_types is None else action_types
    passed = passed or set()

    at = action_types.get(type_name)
    if at is None:
        # A whitelist blocks the unknown by default — an unmodeled action type is a
        # gap to close, not a free pass.
        return Clearance(
            action_type=type_name,
            cleared=False,
            unknown_type=True,
            ceo_importance=1.0,  # unknown risk is treated as maximal until modeled
            financial_weight=financial_weight,
            missing_clearances=["(이 행위 유형이 아직 모델에 없음 — 유형·클리어런스 정의 필요)"],
        )

    auto_flags: list[Flag] = check_campaign(text, date, llm=llm) if at.auto_check == "sensitivity" else []
    missing = [c for c in at.required_clearances if c not in passed]
    cleared = (not auto_flags) and (not missing)
    ceo_importance = max(financial_weight, _amplifier(at.exposure))  # risk floor dominates cost

    return Clearance(
        action_type=type_name,
        cleared=cleared,
        triggered_exposure=list(at.exposure),
        auto_flags=auto_flags,
        missing_clearances=missing,
        ceo_importance=round(ceo_importance, 3),
        financial_weight=financial_weight,
    )
