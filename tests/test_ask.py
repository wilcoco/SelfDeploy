"""The primary door: express a desire → wire it (auto) or own it (routed+tracked)."""
from selfdeploy import (
    ANSWERED,
    ROUTED,
    UNVERIFIED,
    Portfolio,
    ask,
    load_portfolio,
    match_desire,
    save_portfolio,
    track,
)
from selfdeploy.grounding import Evidence, Signal
from selfdeploy.templates import FOODSERVICE_FRANCHISE, INJECTION_MOLDING

AT = "2026-07-08"


def test_match_desire_hits_kpi_and_obligation():
    kpis, obls = match_desire(FOODSERVICE_FRANCHISE, "제품별 마진하고 임원 갑질 관리되나")
    assert "profitability" in kpis
    assert "exec_conduct" in obls


def test_desire_with_no_data_is_routed_with_owner_and_due():
    r = ask("임원 갑질 리스크 관리되나", FOODSERVICE_FRANCHISE, Evidence(), at=AT, due_days=7)
    assert r.matched
    assert all(x.kind == ROUTED for x in r.resolutions)
    routed = r.resolutions[0]
    assert routed.owner and routed.due == "2026-07-15"
    assert "담당자 대기" in r.verdict or "담당자에게" in r.verdict or r.counts[ROUTED] > 0


def test_desire_grounded_in_data_is_auto_answered():
    # profitability needs sales_ledger + cost_allocation + price_ledger
    ev = Evidence(signals=[
        Signal(id="ERP.sales", kind="data", tags=["sales_ledger"]),
        Signal(id="ERP.cost", kind="data", tags=["cost_allocation"]),
        Signal(id="ERP.price", kind="data", tags=["price_ledger"]),
    ])
    r = ask("제품별 마진 알고 싶다", INJECTION_MOLDING, ev, at=AT)
    assert any(x.kind == ANSWERED for x in r.resolutions)
    assert r.counts[ROUTED] == 0
    assert "자동" in r.verdict


def test_partial_answer_mixes_auto_and_routed():
    ev = Evidence(signals=[Signal(id="ERP.sales", kind="data", tags=["sales_ledger"])])
    r = ask("제품별 마진 알고 싶다", INJECTION_MOLDING, ev, at=AT)
    assert r.counts[ANSWERED] >= 1        # sales grounds
    assert r.counts[ROUTED] >= 1          # cost allocation does not
    assert "부분 답" in r.verdict


def test_unknown_desire_escalates_with_owner():
    # a desire no template covers -> escalate (assign a person + new-template mining).
    # (uses a string free of accidental Korean substrings of aliases, e.g. 출하⊂진출하)
    r = ask("블록체인 신사업 검토", INJECTION_MOLDING, Evidence(), at=AT)
    assert r.escalated
    assert r.resolutions[0].owner == "전략"
    assert "템플릿에 없음" in r.verdict


def test_ask_routed_questions_are_trackable(tmp_path):
    r = ask("임원 갑질 관리되나", FOODSERVICE_FRANCHISE, Evidence(), at=AT)
    pf = Portfolio(vertical=FOODSERVICE_FRANCHISE.name)

    class _Item:
        def __init__(s, res):
            s.contract_id, s.label, s.category = res.contract_id, res.label, "욕구"
            s.owner, s.status = res.owner, "사각지대 (미착수)"

    added = track(pf, [_Item(x) for x in r.resolutions if x.kind == ROUTED], at=AT)
    assert added >= 1
    path = tmp_path / "pf.json"
    save_portfolio(pf, path)
    assert load_portfolio(path).items
