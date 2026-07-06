"""Kind-B amortization: a second vertical reuses the whole engine unchanged.

Only templates.py gained a new grammar. The IR, grounding gate, forced
questions, and dual-speed classifier are the same code — here they surface a
*different* hidden layer (CCP measurements and batch lot-links).
"""
from pathlib import Path

from selfdeploy import Grade, ground
from selfdeploy.cli import load_evidence
from selfdeploy.decompose import build_graph
from selfdeploy.evolve import REDESIGN, classify_requirement
from selfdeploy.grounding import Signal
from selfdeploy.interview import MISSING_RECORD, generate_questions
from selfdeploy.templates import FOOD_MANUFACTURING, INJECTION_MOLDING

EX = Path(__file__).resolve().parent.parent / "examples"
REQ = (EX / "food_requirement.txt").read_text(encoding="utf-8")


def _grounded():
    return ground(build_graph(REQ, FOOD_MANUFACTURING), load_evidence(EX / "food_evidence.json"))


def test_both_food_kpis_instantiate():
    g = build_graph(REQ, FOOD_MANUFACTURING)
    assert "kpi:sanitation_compliance:sanitation_compliance" in g.nodes
    assert "kpi:lot_traceability:lot_traceability" in g.nodes


def test_same_engine_surfaces_food_hidden_layer():
    g = _grounded()
    # ERP-backed lots ground; the head/paper cells go red
    assert g.get("kpi:lot_traceability:incoming_lot").grade == Grade.VERIFIED
    assert g.get("kpi:lot_traceability:finished_lot").grade == Grade.VERIFIED
    assert g.get("kpi:lot_traceability:batch_link").grade == Grade.RED
    assert g.get("kpi:sanitation_compliance:ccp_record").grade == Grade.RED
    assert g.get("kpi:sanitation_compliance:ccp_definition").grade == Grade.UNVERIFIED


def test_forced_questions_work_on_new_vertical():
    qs = {q.contract_id: q for q in generate_questions(_grounded())}
    assert qs["kpi:lot_traceability:batch_link"].gap == MISSING_RECORD


def test_classifier_works_on_new_vertical():
    g = build_graph("위생 점검만 보고 싶다", FOOD_MANUFACTURING)  # only sanitation present
    v = classify_requirement("원재료 로트 추적성도 하자", FOOD_MANUFACTURING, g)
    assert v.speed == REDESIGN  # traceability is a new KPI -> new structure


def test_verticals_are_independent():
    # a food traceability requirement maps to nothing in the injection grammar
    assert INJECTION_MOLDING.match("원재료 로트 추적성") == []


def test_keyword_matcher_is_a_crude_fallback():
    # Known limitation, documented not hidden: substring matching is fragile in
    # Korean — '수율'(yield) is a substring of '준수율'(compliance rate), so the
    # offline matcher false-positives here. The --llm mapper is the robust path;
    # the deterministic gate downstream still contains any bad mapping.
    assert "defect_rate" in INJECTION_MOLDING.match("준수율")
