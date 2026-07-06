from pathlib import Path

from selfdeploy import Grade, ground, metrics
from selfdeploy.cli import load_evidence
from selfdeploy.decompose import build_graph
from selfdeploy.grounding import Evidence, Signal
from selfdeploy.ir import Contract, ContractGraph, NodeKind
from selfdeploy.templates import INJECTION_MOLDING

EVIDENCE = Path(__file__).resolve().parent.parent / "examples" / "injection_molding_evidence.json"


def _grounded():
    graph = build_graph(Path(EVIDENCE.parent, "requirement.txt").read_text(encoding="utf-8"), INJECTION_MOLDING)
    return ground(graph, load_evidence(EVIDENCE))


def test_data_backed_record_is_verified():
    g = _grounded()
    assert g.get("kpi:defect_rate:production_denominator").grade == Grade.VERIFIED


def test_missing_record_is_red():
    g = _grounded()
    # neither inspection nor disposition is recorded -> the hidden layer, surfaced
    assert g.get("kpi:defect_rate:inspection_record").grade == Grade.RED
    assert g.get("kpi:defect_rate:disposition_record").grade == Grade.RED


def test_claim_only_is_unverified():
    g = _grounded()
    # defect definition exists only as a manual sentence -> declared, not verified
    assert g.get("kpi:defect_rate:defect_definition").grade == Grade.UNVERIFIED


def test_owned_judgment_is_not_red():
    g = _grounded()
    assert g.get("kpi:downtime:reason_code").grade == Grade.JUDGMENT
    assert g.get("kpi:downtime:reason_code").owner == "생산반장"


def test_unowned_judgment_is_red():
    g = _grounded()
    # borderline defect call has no acknowledged owner -> still a gap
    assert g.get("kpi:defect_rate:borderline_call").grade == Grade.RED


def test_kpi_is_only_as_trustworthy_as_weakest_record():
    g = _grounded()
    # defect_rate has red leaves -> the whole KPI is red, however nice the dashboard looks
    assert g.get("kpi:defect_rate:defect_rate").grade == Grade.RED
    # downtime grounds in data, with one acknowledged human classification
    assert g.get("kpi:downtime:downtime").grade == Grade.JUDGMENT


def test_red_density_is_reported():
    g = _grounded()
    m = metrics(g)
    assert m.total > 0
    assert m.red > 0
    assert 0.0 < m.red_density < 1.0


def test_grounding_is_deterministic():
    assert _grounded().get("kpi:defect_rate:defect_rate").grade == _grounded().get(
        "kpi:defect_rate:defect_rate"
    ).grade


def test_direct_grade_unit():
    # a hand-built two-node graph: root requires one data-backed leaf
    g = ContractGraph(root_id="r")
    g.add(Contract(id="r", label="root", kind=NodeKind.KPI, requires=["leaf"]))
    g.add(Contract(id="leaf", label="leaf", kind=NodeKind.RECORD, grounding_tags=["x"]))
    ground(g, Evidence(signals=[Signal(id="s", kind="data", tags=["x"])]))
    assert g.get("leaf").grade == Grade.VERIFIED
    assert g.get("r").grade == Grade.VERIFIED
