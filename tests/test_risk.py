from selfdeploy import (
    CATASTROPHIC,
    Grade,
    build_obligation_graph,
    effective_severity,
    escalate,
    ground,
    risk_register,
)
from selfdeploy.grounding import Evidence, Signal
from selfdeploy.templates import FOOD_MANUFACTURING, INJECTION_MOLDING


def test_obligation_graph_instantiates_accountability_surface():
    g = build_obligation_graph(FOOD_MANUFACTURING)
    assert "obl:consumer_safety:consumer_safety" in g.nodes
    assert "obl:consumer_safety:recall_traceability" in g.nodes


def test_controls_inherit_obligation_severity():
    g = build_obligation_graph(FOOD_MANUFACTURING)
    eff = effective_severity(g)
    # a control under consumer_safety (CATASTROPHIC) inherits the blast radius
    assert eff["obl:consumer_safety:foreign_body_control"] == CATASTROPHIC


def test_register_ranks_catastrophic_ungrounded_first():
    g = ground(build_obligation_graph(FOOD_MANUFACTURING), Evidence())
    reg = risk_register(g)
    assert reg  # non-empty
    assert reg[0].risk == max(i.risk for i in reg)
    # with no evidence, top item is a catastrophic + red control
    assert reg[0].severity == CATASTROPHIC
    assert reg[0].grade == Grade.RED


def test_grounding_a_control_lowers_its_risk():
    g0 = ground(build_obligation_graph(FOOD_MANUFACTURING), Evidence())
    ev = Evidence(signals=[Signal(id="MD.log", kind="data", tags=["metal_detector_log"])])
    g1 = ground(build_obligation_graph(FOOD_MANUFACTURING), ev)
    r0 = {i.contract_id: i for i in risk_register(g0)}
    r1 = {i.contract_id: i for i in risk_register(g1)}
    fb = "obl:consumer_safety:foreign_body_control"
    assert r0[fb].risk > 0
    assert fb not in r1  # grounded -> VERIFIED -> drops off the register entirely


def test_human_only_control_flagged():
    g = ground(build_obligation_graph(FOOD_MANUFACTURING), Evidence())
    reg = {i.contract_id: i for i in risk_register(g)}
    # recall traceability needs batch_link, which no collector covers
    assert reg["obl:consumer_safety:recall_traceability"].human_only is True


def test_escalation_splits_ceo_from_ops():
    g = ground(build_obligation_graph(INJECTION_MOLDING), Evidence())
    reg = risk_register(g)
    ceo, ops = escalate(reg, 2)
    assert len(ceo) == 2
    assert len(ceo) + len(ops) == len(reg)
    # the catastrophic worker-safety controls should outrank the severe liability ones
    assert ceo[0].severity >= ceo[-1].severity


def test_worker_safety_catastrophic_outranks_product_liability_severe():
    g = ground(build_obligation_graph(INJECTION_MOLDING), Evidence())
    reg = {i.contract_id: i for i in risk_register(g)}
    loto = reg["obl:worker_safety:loto_record"].risk            # CATASTROPHIC x RED = 1.0
    material = reg["obl:product_liability:material_cert"].risk  # SEVERE x RED = 0.75
    assert loto > material
