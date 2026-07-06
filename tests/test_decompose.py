from selfdeploy import Grade, NodeKind
from selfdeploy.decompose import build_graph
from selfdeploy.templates import INJECTION_MOLDING


def test_requirement_maps_to_matching_kpis():
    graph = build_graph("라인별 불량률과 가동중단을 보고 싶다", INJECTION_MOLDING)
    root = graph.root
    assert root.kind == NodeKind.REQUIREMENT
    labels = {graph.get(cid).kind for cid in root.requires}
    assert NodeKind.KPI in labels
    # both defect_rate and downtime KPI roots present
    assert "kpi:defect_rate:defect_rate" in graph.nodes
    assert "kpi:downtime:downtime" in graph.nodes


def test_unmatched_requirement_becomes_red_unknown():
    graph = build_graph("직원 복지 제도를 개선하고 싶다", INJECTION_MOLDING)
    assert "req:unknown" in graph.nodes
    unknown = graph.get("req:unknown")
    assert unknown.kind == NodeKind.UNKNOWN
    assert unknown.grade == Grade.RED


def test_entailment_substructure_is_instantiated():
    graph = build_graph("불량률", INJECTION_MOLDING)
    # the KPI entails its records — the "ought" substructure exists as nodes
    for leaf in ("defect_definition", "inspection_record", "production_denominator", "disposition_record"):
        assert f"kpi:defect_rate:{leaf}" in graph.nodes
