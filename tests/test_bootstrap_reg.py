"""Door-B bootstrap (auto-infer + exceptions), regulation mapping, board HTML."""
from selfdeploy import (
    assign_owners,
    bootstrap,
    build_obligation_graph,
    effective_regulations,
    ground,
    risk_register,
    risk_register_html,
)
from selfdeploy.grounding import Evidence
from selfdeploy.risk import escalate
from selfdeploy.templates import FOOD_MANUFACTURING, INJECTION_MOLDING


def _inj():
    return ground(build_obligation_graph(INJECTION_MOLDING), Evidence())


# --- ① bootstrap ---------------------------------------------------------- #

def test_bootstrap_auto_assigns_matched_and_flags_exceptions():
    g = _inj()
    # org chart covers 정비/품질 but not 구매/생산/안전 -> those are exceptions
    org = {"roles": [
        {"role": "정비", "owner": "박정비", "aliases": ["설비보전"]},
        {"role": "품질", "owner": "김검사", "aliases": ["QC"]},
    ]}
    result = bootstrap(g, org)
    assign_owners(g, result.resolver)
    assert g.get("obl:worker_safety:loto_record").owner == "박정비"      # matched (alias)
    assert g.get("obl:product_liability:defect_escape_control").owner == "김검사"  # matched
    unmatched_roles = {role for _id, _label, role in result.exceptions}
    assert {"구매", "생산", "안전"} <= unmatched_roles                    # misses surfaced
    assert "정비" not in unmatched_roles and "품질" not in unmatched_roles


def test_bootstrap_alias_matches():
    g = _inj()
    result = bootstrap(g, {"roles": [{"role": "정비팀", "owner": "박정비", "aliases": ["정비"]}]})
    assign_owners(g, result.resolver)
    assert g.get("obl:worker_safety:loto_record").owner == "박정비"


def test_bootstrap_exceptions_are_deduped_by_role():
    g = ground(build_obligation_graph(FOOD_MANUFACTURING), Evidence())
    result = bootstrap(g, {})  # empty org -> every role is an exception, once each
    roles = [role for _id, _label, role in result.exceptions]
    assert len(roles) == len(set(roles))


# --- ② regulation mapping ------------------------------------------------- #

def test_controls_inherit_obligation_regulations():
    g = build_obligation_graph(INJECTION_MOLDING)
    regs = effective_regulations(g)
    assert "중대재해처벌법" in regs["obl:worker_safety:loto_record"]
    assert "제조물책임법" in regs["obl:product_liability:material_cert"]


def test_register_items_carry_regulations():
    reg = {i.contract_id: i for i in risk_register(_inj())}
    assert "중대재해처벌법" in reg["obl:worker_safety:loto_record"].regulations
    # a worker-safety control does not carry the product-liability law
    assert "제조물책임법" not in reg["obl:worker_safety:loto_record"].regulations


# --- ③ board HTML --------------------------------------------------------- #

def test_board_html_renders_key_fields():
    g = _inj()
    ceo, ops = escalate(risk_register(g), 2)
    doc = risk_register_html(INJECTION_MOLDING.name, ceo, ops, 2)
    assert "대표 리스크 레지스터" in doc
    assert "중대재해처벌법" in doc          # regulation column populated
    assert "@media print" in doc            # print-to-PDF ready
    assert "근거 법규" in doc               # header present
