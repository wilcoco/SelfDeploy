from selfdeploy.decompose import build_graph
from selfdeploy.evolve import (
    CONTINUOUS,
    PROMOTE,
    REDESIGN,
    classify_requirement,
    classify_signal,
)
from selfdeploy.grounding import Signal
from selfdeploy.templates import INJECTION_MOLDING

# graph with defect_rate + downtime instantiated
GRAPH = build_graph("불량률과 가동중단을 보고 싶다", INJECTION_MOLDING)


def test_existing_tag_is_continuous():
    v = classify_signal(GRAPH, Signal(id="s", kind="data", tags=["production_count"]))
    assert v.speed == CONTINUOUS


def test_tag_of_still_missing_contract_is_continuous():
    # inspection_log is expected by a (currently red) contract — feeding it is still fast-pulse
    v = classify_signal(GRAPH, Signal(id="s", kind="data", tags=["inspection_log"]))
    assert v.speed == CONTINUOUS


def test_wholly_novel_tag_is_redesign():
    v = classify_signal(GRAPH, Signal(id="s", kind="data", tags=["paint_gloss_meter"]))
    assert v.speed == REDESIGN
    assert v.novel_tags == ["paint_gloss_meter"]


def test_partial_match_is_promote():
    # the trap: looks like more inspection data, but carries a new rework route
    v = classify_signal(
        GRAPH, Signal(id="s", kind="data", tags=["inspection_log", "new_rework_route"])
    )
    assert v.speed == PROMOTE
    assert "inspection_log" in v.matched_tags
    assert "new_rework_route" in v.novel_tags


def test_requirement_for_existing_kpi_is_continuous():
    assert classify_requirement("불량률을 더 자주 보고 싶다", INJECTION_MOLDING, GRAPH).speed == CONTINUOUS


def test_requirement_for_new_kpi_is_redesign():
    v = classify_requirement("납기 준수율도 관리하자", INJECTION_MOLDING, GRAPH)
    assert v.speed == REDESIGN
    assert "on_time_delivery" in v.novel_tags


def test_unknown_requirement_is_redesign():
    assert classify_requirement("직원 복지 개선", INJECTION_MOLDING, GRAPH).speed == REDESIGN
