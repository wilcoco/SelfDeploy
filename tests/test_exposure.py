"""Exposure classes: legal is only one consequence axis (the Starbucks lesson)."""
from selfdeploy import (
    build_obligation_graph,
    by_exposure,
    effective_exposure,
    ground,
    risk_register,
    risk_register_html,
)
from selfdeploy.grounding import Evidence
from selfdeploy.risk import escalate
from selfdeploy.templates import FOODSERVICE_FRANCHISE, INJECTION_MOLDING


def test_controls_inherit_exposure_classes():
    g = build_obligation_graph(FOODSERVICE_FRANCHISE)
    exp = effective_exposure(g)
    promo = exp["obl:promo_operational_load:staffing_record"]
    assert "브랜드·여론" in promo and "정치" in promo and "노무·ESG" in promo


def test_starbucks_shaped_risk_is_non_legal():
    # the promo obligation carries a weak legal citation but strong non-legal exposure
    g = ground(build_obligation_graph(FOODSERVICE_FRANCHISE), Evidence())
    reg = {i.contract_id: i for i in risk_register(g)}
    staffing = reg["obl:promo_operational_load:staffing_record"]
    assert "브랜드·여론" in staffing.exposure
    assert "정치" in staffing.exposure
    # its exposure is broader than what the single labor law would suggest
    assert set(staffing.exposure) - {"법규"}  # there is non-legal exposure


def test_by_exposure_rollup_surfaces_non_legal_classes():
    g = ground(build_obligation_graph(FOODSERVICE_FRANCHISE), Evidence())
    classes = {k for k, _ in by_exposure(risk_register(g))}
    # a purely legal rollup would never show these
    assert {"브랜드·여론", "정치", "노무·ESG", "안전·생명"} <= classes


def test_by_exposure_items_actually_carry_the_class():
    g = ground(build_obligation_graph(INJECTION_MOLDING), Evidence())
    for cls, items in by_exposure(risk_register(g)):
        assert all(cls in (i.exposure or []) for i in items)


def test_board_html_shows_exposure_badges():
    g = ground(build_obligation_graph(FOODSERVICE_FRANCHISE), Evidence())
    ceo, ops = escalate(risk_register(g), 4)
    doc = risk_register_html(FOODSERVICE_FRANCHISE.name, ceo, ops, 4)
    assert "노출" in doc            # exposure column header
    assert "브랜드·여론" in doc      # non-legal class rendered
