"""Owner resolution (3 options) + routing so cascade distributes, not dumps."""
from types import SimpleNamespace

from selfdeploy import (
    assign_owners,
    build_obligation_graph,
    by_owner,
    ground,
    manual_resolver,
    org_chart_resolver,
    risk_register,
    template_resolver,
)
from selfdeploy.grounding import Evidence
from selfdeploy.owners import LLMOwnerResolver
from selfdeploy.templates import INJECTION_MOLDING


def _graph():
    return ground(build_obligation_graph(INJECTION_MOLDING), Evidence())


def test_template_resolver_uses_role_seed():
    g = assign_owners(_graph(), template_resolver())
    assert g.get("obl:worker_safety:loto_record").owner == "정비"


def test_org_chart_resolver_maps_role_to_person():
    g = assign_owners(_graph(), org_chart_resolver({"정비": "박정비"}))
    assert g.get("obl:worker_safety:loto_record").owner == "박정비"
    # unmapped role falls back to the template role
    assert g.get("obl:product_liability:material_cert").owner == "구매"


def test_manual_resolver_overrides_by_id_and_tag():
    g = assign_owners(
        _graph(),
        manual_resolver({"obl:worker_safety:loto_record": "특정담당", "material_cert": "구매과장"}),
    )
    assert g.get("obl:worker_safety:loto_record").owner == "특정담당"
    assert g.get("obl:product_liability:material_cert").owner == "구매과장"


def test_routing_groups_register_by_owner():
    g = assign_owners(_graph(), template_resolver())
    buckets = by_owner(risk_register(g))
    assert "정비" in buckets and "품질" in buckets
    # every item in a bucket belongs to that owner
    for owner, items in buckets.items():
        assert all(i.owner == owner for i in items)


def test_llm_resolver_gate_falls_back_on_unknown_role():
    # injected fake client returns a role not in the candidate set -> fall back to template role
    fake = SimpleNamespace(
        messages=SimpleNamespace(
            create=lambda **kw: SimpleNamespace(
                content=[SimpleNamespace(type="text", text='{"role": "마케팅"}')]
            )
        )
    )
    g = _graph()
    resolver = LLMOwnerResolver(roles=["정비", "품질", "구매", "생산", "안전"], client=fake)
    node = g.get("obl:worker_safety:loto_record")
    assert resolver(node) == "정비"  # 마케팅 rejected by the gate -> template role


def test_llm_resolver_accepts_valid_role():
    fake = SimpleNamespace(
        messages=SimpleNamespace(
            create=lambda **kw: SimpleNamespace(
                content=[SimpleNamespace(type="text", text='{"role": "안전"}')]
            )
        )
    )
    resolver = LLMOwnerResolver(roles=["정비", "품질", "구매", "생산", "안전"], client=fake)
    node = _graph().get("obl:worker_safety:loto_record")
    assert resolver(node) == "안전"
