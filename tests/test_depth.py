"""Obligation depth (privacy/env/financial), 3rd vertical, regulation rollup, LLM org."""
from types import SimpleNamespace

from selfdeploy import build_obligation_graph, by_regulation, ground, risk_register
from selfdeploy.grounding import Evidence
from selfdeploy.owners import LLMOrgInferer, bootstrap
from selfdeploy.templates import FOODSERVICE_FRANCHISE, INJECTION_MOLDING, VERTICALS


def test_cross_cutting_obligations_present_everywhere():
    for v in (INJECTION_MOLDING, FOODSERVICE_FRANCHISE):
        assert "privacy" in v.obligations
        assert "financial_control" in v.obligations


def test_third_vertical_registered():
    assert "foodservice_franchise" in VERTICALS


def test_foodservice_promo_load_is_the_starbucks_shaped_obligation():
    g = build_obligation_graph(FOODSERVICE_FRANCHISE)
    assert "obl:promo_operational_load:staffing_record" in g.nodes
    assert "obl:promo_operational_load:load_threshold_alarm" in g.nodes


def test_regulation_rollup_groups_by_law():
    g = ground(build_obligation_graph(INJECTION_MOLDING), Evidence())
    groups = dict(by_regulation(risk_register(g)))
    assert "중대재해처벌법" in groups
    assert "개인정보보호법" in groups
    # every item under a law actually cites that law
    for law, items in groups.items():
        assert all(law in (i.regulations or []) for i in items)


def test_regulation_rollup_sorted_by_worst_risk():
    g = ground(build_obligation_graph(INJECTION_MOLDING), Evidence())
    groups = by_regulation(risk_register(g))
    tops = [max(i.risk for i in items) for _law, items in groups]
    assert tops == sorted(tops, reverse=True)


def test_llm_org_inferer_gates_to_known_roles():
    fake = SimpleNamespace(
        messages=SimpleNamespace(
            create=lambda **kw: SimpleNamespace(
                content=[SimpleNamespace(
                    type="text",
                    text='{"roles":[{"role":"정비","owner":"박정비","aliases":["설비"]},'
                         '{"role":"마케팅부","owner":"엉뚱","aliases":[]}]}',
                )]
            )
        )
    )
    inferer = LLMOrgInferer(known_roles=["정비", "품질", "안전"], description="…", client=fake)
    org = inferer.infer()
    roles = {r["role"] for r in org["roles"]}
    assert roles == {"정비"}  # 마케팅부 not in known_roles -> gated out


def test_llm_org_feeds_bootstrap():
    fake = SimpleNamespace(
        messages=SimpleNamespace(
            create=lambda **kw: SimpleNamespace(
                content=[SimpleNamespace(type="text", text='{"roles":[{"role":"정비","owner":"박정비"}]}')]
            )
        )
    )
    g = ground(build_obligation_graph(INJECTION_MOLDING), Evidence())
    org = LLMOrgInferer(["정비"], "박정비가 설비 담당", client=fake).infer()
    result = bootstrap(g, org)
    from selfdeploy import assign_owners

    assign_owners(g, result.resolver)
    assert g.get("obl:worker_safety:loto_record").owner == "박정비"
