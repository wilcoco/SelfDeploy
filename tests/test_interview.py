from pathlib import Path

from selfdeploy import Grade
from selfdeploy.cli import load_answers, load_evidence
from selfdeploy.decompose import build_graph
from selfdeploy.grounding import ground, metrics
from selfdeploy.interview import (
    CLAIM_ONLY,
    MISSING_RECORD,
    UNOWNED_JUDGMENT,
    generate_questions,
    run_round,
)
from selfdeploy.templates import INJECTION_MOLDING

EX = Path(__file__).resolve().parent.parent / "examples"
REQ = (EX / "requirement.txt").read_text(encoding="utf-8")


def _grounded():
    return ground(build_graph(REQ, INJECTION_MOLDING), load_evidence(EX / "injection_molding_evidence.json"))


def test_questions_generated_from_type_non_closure():
    qs = {q.contract_id: q for q in generate_questions(_grounded())}
    assert qs["kpi:defect_rate:inspection_record"].gap == MISSING_RECORD
    assert qs["kpi:defect_rate:borderline_call"].gap == UNOWNED_JUDGMENT
    assert qs["kpi:defect_rate:defect_definition"].gap == CLAIM_ONLY


def test_only_leaves_and_specials_get_questions():
    # a red *parent* (inspection_event) is a consequence, not its own question
    ids = {q.contract_id for q in generate_questions(_grounded())}
    assert "kpi:defect_rate:inspection_event" not in ids
    assert "kpi:defect_rate:defect_rate" not in ids


def test_questions_sorted_missing_before_claim():
    qs = generate_questions(_grounded())
    gaps = [q.gap for q in qs]
    assert gaps.index(MISSING_RECORD) < gaps.index(CLAIM_ONLY)


def test_answers_close_red_cells():
    evidence = load_evidence(EX / "injection_molding_evidence.json")
    answers = load_answers(EX / "answers.json")
    graph, _, rnd = run_round(REQ, INJECTION_MOLDING, evidence, answers)
    assert rnd.before.red == 7
    assert rnd.after.red == 0
    assert rnd.red_closed == 7


def test_answer_grades_reflect_data_vs_plan():
    evidence = load_evidence(EX / "injection_molding_evidence.json")
    answers = load_answers(EX / "answers.json")
    graph, _, _ = run_round(REQ, INJECTION_MOLDING, evidence, answers)
    # a plan (claim) grounds to UNVERIFIED, real data to VERIFIED, owner to JUDGMENT
    assert graph.get("kpi:defect_rate:inspection_record").grade == Grade.UNVERIFIED
    assert graph.get("kpi:defect_rate:disposition_record").grade == Grade.VERIFIED
    assert graph.get("kpi:defect_rate:borderline_call").grade == Grade.JUDGMENT
    assert graph.get("kpi:defect_rate:defect_definition").grade == Grade.VERIFIED
    # KPI moves RED -> UNVERIFIED: committed but not yet data-corroborated (honest)
    assert graph.get("kpi:defect_rate:defect_rate").grade == Grade.UNVERIFIED


def test_shared_tag_answer_closes_multiple_cells():
    # inspection_record's signal carries tag inspection_log, which also grounds defect_count
    evidence = load_evidence(EX / "injection_molding_evidence.json")
    answers = load_answers(EX / "answers.json")
    graph, _, _ = run_round(REQ, INJECTION_MOLDING, evidence, answers)
    assert graph.get("kpi:defect_rate:defect_count").grade == Grade.UNVERIFIED
