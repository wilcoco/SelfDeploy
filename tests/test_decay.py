"""Temporal decay: a data grounding nobody re-confirms stops being trusted."""
from selfdeploy import Grade, ground
from selfdeploy.decompose import build_graph
from selfdeploy.grounding import Evidence, Signal
from selfdeploy.templates import INJECTION_MOLDING

DENOM = "kpi:defect_rate:production_denominator"  # has freshness = 1.0


def _graph_with_count(as_of):
    graph = build_graph("불량률", INJECTION_MOLDING)
    ev = Evidence(signals=[Signal(id="MES.count", kind="data", tags=["production_count"], as_of=as_of)])
    return graph, ev


def test_fresh_data_is_verified():
    g, ev = _graph_with_count(as_of=0.0)
    ground(g, ev, as_of=0.5)  # age 0.5 <= freshness 1.0
    assert g.get(DENOM).grade == Grade.VERIFIED


def test_stale_data_decays_to_unverified():
    g, ev = _graph_with_count(as_of=0.0)
    ground(g, ev, as_of=3.0)  # age 3.0 > freshness 1.0
    assert g.get(DENOM).grade == Grade.UNVERIFIED
    assert "부식" in g.get(DENOM).note


def test_no_eval_time_means_no_decay():
    g, ev = _graph_with_count(as_of=0.0)
    ground(g, ev)  # as_of=None -> timeless grounding, back-compatible
    assert g.get(DENOM).grade == Grade.VERIFIED


def test_signal_without_timestamp_never_stales():
    g, ev = _graph_with_count(as_of=None)
    ground(g, ev, as_of=999.0)  # signal has no as_of -> cannot be judged stale
    assert g.get(DENOM).grade == Grade.VERIFIED
