"""The management loop: propose (perf + risk) -> select -> cascade -> manage."""
from selfdeploy import (
    cascade,
    management_surface,
    select,
    status_summary,
)
from selfdeploy.grounding import Evidence
from selfdeploy.templates import FOODSERVICE_FRANCHISE


def _surface(requirement=""):
    return management_surface(FOODSERVICE_FRANCHISE, Evidence(), requirement=requirement)


def test_surface_unifies_risk_and_performance_lenses():
    with_perf = _surface(requirement="위생 점검 준수율을 보고 싶다")
    codes = {i.category_code for i in with_perf}
    assert any(c.startswith("C") for c in codes)  # risk categories
    assert any(c.startswith("P") for c in codes)  # performance categories (P1~P4)


def test_surface_status_is_management_framed_not_defensive():
    for it in _surface():
        assert it.status in {"관리중 (확보)", "사람이 관리중", "진행중 (미확정)", "사각지대 (미착수)"}


def test_select_by_category():
    surface = _surface()
    picked = select(surface, codes={"C4"})
    assert picked
    assert all(i.category_code == "C4" for i in picked)


def test_select_top_n():
    surface = _surface()
    assert len(select(surface, top=3)) == 3


def test_cascade_routes_to_owners():
    surface = _surface()
    picked = select(surface, codes={"C4"})
    buckets = cascade(picked)
    assert buckets
    for owner, items in buckets.items():
        assert all(i.owner == owner for i in items)


def test_status_summary_counts():
    surface = _surface()
    summ = status_summary(surface)
    assert sum(summ.values()) == len(surface)


def test_surface_sorted_by_weight_desc():
    surface = _surface()
    weights = [i.weight for i in surface]
    assert weights == sorted(weights, reverse=True)
