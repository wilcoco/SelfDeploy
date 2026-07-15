"""The three management-loop upgrades: persistence, perf categories, rationale."""
from selfdeploy import (
    Portfolio,
    current_statuses,
    load_portfolio,
    management_surface,
    progress,
    rationale,
    save_portfolio,
    select,
    snapshot,
    track,
)
from selfdeploy.categories import PERF_CATEGORIES, kpi_category
from selfdeploy.grounding import Evidence, Signal
from selfdeploy.templates import FOODSERVICE_FRANCHISE, INJECTION_MOLDING


# --- ② performance categories ------------------------------------------------ #

def test_perf_kpis_exist_on_every_vertical():
    for v in (INJECTION_MOLDING, FOODSERVICE_FRANCHISE):
        for key in ("profitability", "cost_visibility", "sales_growth"):
            assert key in v.kpis


def test_kpi_category_mapping():
    assert kpi_category("profitability")[0] == "P1"
    assert kpi_category("defect_rate")[0] == "P4"
    assert kpi_category("unknown_kpi")[0] == "P?"


def test_surface_without_requirement_includes_full_perf_grammar():
    surface = management_surface(FOODSERVICE_FRANCHISE, Evidence())
    codes = {i.category_code for i in surface}
    assert {"P1", "P2", "P3"} <= codes          # perf lens present by default
    assert any(c.startswith("C") for c in codes)  # risk lens too


def test_perf_and_risk_selectable_together():
    surface = management_surface(FOODSERVICE_FRANCHISE, Evidence())
    picked = select(surface, codes={"P1", "C4"})
    assert {i.category_code for i in picked} == {"P1", "C4"}


# --- ③ rationale -------------------------------------------------------------- #

def test_rationale_cites_real_cases_for_risk_category():
    surface = management_surface(FOODSERVICE_FRANCHISE, Evidence())
    c4 = select(surface, codes={"C4"})[0]
    reasons = " ".join(rationale(c4))
    assert "낙마 사례" in reasons and "땅콩회항" in reasons


def test_rationale_flags_quick_win_vs_people_gate():
    surface = management_surface(INJECTION_MOLDING, Evidence())
    texts = {i.contract_id: " ".join(rationale(i)) for i in surface}
    # inspection escape control is sensor-closeable -> quick win
    assert "착수 비용 낮음" in texts["obl:product_liability:defect_escape_control"]
    # gapjil monitoring needs a people gate
    assert "사람 게이트" in texts["obl:exec_conduct:gapjil_monitoring"]


def test_rationale_marks_stalled():
    surface = management_surface(FOODSERVICE_FRANCHISE, Evidence())
    reasons = rationale(surface[0], stalled_reviews=3)
    assert any("정체" in r for r in reasons)


# --- ① persistence ------------------------------------------------------------ #

def _cheap_portfolio():
    surface = management_surface(FOODSERVICE_FRANCHISE, Evidence())
    picked = select(surface, codes={"P1"})     # profitability controls, all 사각지대
    pf = Portfolio(vertical=FOODSERVICE_FRANCHISE.name)
    track(pf, picked, at="2026-07-01")
    return pf


def test_track_records_initial_status():
    pf = _cheap_portfolio()
    assert pf.items
    for t in pf.items.values():
        assert t.first_status == "사각지대 (미착수)"


def test_snapshot_detects_improvement():
    pf = _cheap_portfolio()
    # sales ledger arrives -> two P1 controls ground (sales_ledger + price? no, discount uses price_ledger)
    ev = Evidence(signals=[Signal(id="ERP.sales", kind="data", tags=["sales_ledger"])])
    moved = snapshot(pf, current_statuses(FOODSERVICE_FRANCHISE, ev), at="2026-07-08")
    assert moved >= 1
    summ = progress(pf)
    assert summ.improved >= 1
    assert 0 < summ.graduation_rate <= 1


def test_stalled_detection_after_two_flat_reviews():
    pf = _cheap_portfolio()
    empty = current_statuses(FOODSERVICE_FRANCHISE, Evidence())
    snapshot(pf, empty, at="2026-07-08")
    snapshot(pf, empty, at="2026-07-15")
    summ = progress(pf)
    assert summ.stalled == summ.total          # nothing ever moved


def test_portfolio_roundtrip(tmp_path):
    pf = _cheap_portfolio()
    snapshot(pf, current_statuses(FOODSERVICE_FRANCHISE, Evidence()), at="2026-07-08")
    path = tmp_path / "pf.json"
    save_portfolio(pf, path)
    loaded = load_portfolio(path)
    assert loaded.vertical == pf.vertical
    assert set(loaded.items) == set(pf.items)
    assert loaded.reviews == pf.reviews
    any_item = next(iter(loaded.items.values()))
    assert len(any_item.history) == 2
