from selfdeploy import Grade, ground
from selfdeploy.collectors import (
    DEFAULT_CATALOG,
    collect_all,
    data_source_collector,
    plan_sensing,
    predictive_maintenance_collector,
)
from selfdeploy.decompose import build_graph
from selfdeploy.grounding import Evidence
from selfdeploy.templates import FOOD_MANUFACTURING, INJECTION_MOLDING

READINGS = [
    {"device": "INJ-03", "value": 12.1, "ts": 0.0, "state": "baseline"},
    {"device": "INJ-03", "value": 0.2, "ts": 4.0, "state": "dropout"},
    {"device": "INJ-03", "value": 12.3, "ts": 5.0, "state": "baseline"},
]


def test_pm_collector_produces_machine_signals():
    sigs = predictive_maintenance_collector(READINGS).collect()
    tags = {t for s in sigs for t in s.tags}
    assert "machine_state" in tags
    assert "downtime_log" in tags  # dropout present
    # as_of is the latest reading timestamp (5.0), dropout ts (4.0)
    assert max(s.as_of for s in sigs) == 5.0


def test_pm_collector_no_dropout_no_downtime():
    calm = [{"device": "X", "value": 1.0, "ts": 1.0, "state": "baseline"}]
    tags = {t for s in predictive_maintenance_collector(calm).collect() for t in s.tags}
    assert "downtime_log" not in tags


def test_collected_signals_ground_downtime_kpi():
    graph = build_graph("가동중단을 보고 싶다", INJECTION_MOLDING)
    merged = collect_all([predictive_maintenance_collector(READINGS)], Evidence())
    ground(graph, merged)
    # downtime record grounds from the machine feed
    assert graph.get("kpi:downtime:stop_record").grade == Grade.VERIFIED


def test_plan_partitions_sensor_vs_human_only():
    graph = ground(build_graph("불량률", INJECTION_MOLDING), Evidence())
    plans = {p.contract_id: p for p in plan_sensing(graph)}
    # inspection record is closeable by the QC scan gate
    insp = plans["kpi:defect_rate:inspection_record"]
    assert "QC-scan-gate" in insp.candidates and not insp.human_only
    # a defect definition can be weakly filled by document extraction
    defn = plans["kpi:defect_rate:defect_definition"]
    assert defn.best_strength == "weak"


def test_food_hidden_layer_is_human_only():
    graph = ground(build_graph("원재료 로트 추적성", FOOD_MANUFACTURING), Evidence())
    plans = {p.contract_id: p for p in plan_sensing(graph)}
    # batch lot-link lives in a worker's head — no collector covers it
    assert plans["kpi:lot_traceability:batch_link"].human_only is True


def test_machine_feed_grounds_stop_but_not_the_human_reason():
    # The honest partition: the machine feed closes the stop event, but the stop
    # *reason* is a human classification no sensor can produce.
    graph = build_graph("가동중단을 보고 싶다", INJECTION_MOLDING)
    merged = collect_all([predictive_maintenance_collector(READINGS)], Evidence())
    ground(graph, merged)
    assert graph.get("kpi:downtime:stop_record").grade == Grade.VERIFIED
    assert graph.get("kpi:downtime:reason_code").grade == Grade.RED  # unowned judgment
    assert graph.get("kpi:downtime:downtime").grade == Grade.RED     # KPI blocked by the human cell
