"""Default-deny whitelist gate: silence is not clearance; risk-touch amplifies importance."""
from selfdeploy import clear_action


def test_tankday_is_blocked_by_the_gate():
    c = clear_action("campaign", text="탱크데이 — 책상에 탁!", date="2026-05-18")
    assert c.cleared is False
    assert c.auto_flags                      # sensitivity flags fired
    assert "campaign_sensitivity_review" in c.missing_clearances


def test_silence_is_not_clearance():
    # a clean campaign with NO auto flags is STILL blocked until reviewed (whitelist)
    c = clear_action("campaign", text="여름 신메뉴 출시", date="2026-07-01")
    assert not c.auto_flags
    assert c.cleared is False               # default-deny — absence of a flag ≠ safe
    assert "campaign_sensitivity_review" in c.missing_clearances


def test_affirmative_clearance_passes():
    c = clear_action("campaign", text="여름 신메뉴 출시", date="2026-07-01",
                     passed={"campaign_sensitivity_review"})
    assert c.cleared is True


def test_flagged_campaign_blocked_even_with_review_passed():
    # even a passed review cannot clear a campaign the auto-check flags
    c = clear_action("campaign", text="탱크데이 책상에 탁", date="2026-05-18",
                     passed={"campaign_sensitivity_review"})
    assert c.cleared is False
    assert c.auto_flags


def test_ceo_importance_amplified_by_risk_not_cost():
    # tiny financial weight, but touches 역사·사회 (weight 1.0) -> importance floored at 1.0
    cheap_risky = clear_action("campaign", text="여름 이벤트", date="2026-07-01", financial_weight=0.05)
    assert cheap_risky.ceo_importance == 1.0
    # a big-budget purely-financial action ranks below the cheap risky one
    big_safe = clear_action("fund_disbursement", financial_weight=0.9)
    assert big_safe.ceo_importance >= 0.9  # financial floor
    assert cheap_risky.ceo_importance > big_safe.ceo_importance or big_safe.ceo_importance == 0.9


def test_unknown_action_type_is_blocked_by_default():
    c = clear_action("some_new_thing")
    assert c.cleared is False
    assert c.unknown_type is True
    assert c.ceo_importance == 1.0          # unknown risk treated as maximal until modeled
