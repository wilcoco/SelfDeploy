"""Category taxonomy grounded in cases, and the obligations that now cover the gaps."""
from selfdeploy import (
    CATASTROPHIC,
    RISK_CATEGORIES,
    build_obligation_graph,
    coverage,
    ground,
    risk_register,
)
from selfdeploy.categories import RiskCategory
from selfdeploy.grounding import Evidence
from selfdeploy.templates import FOODSERVICE_FRANCHISE, INJECTION_MOLDING, VERTICALS


def test_new_obligations_added_to_verticals():
    for key in ("exec_conduct", "workplace_culture", "partner_fairness"):
        assert key in INJECTION_MOLDING.obligations
    for key in ("exec_conduct", "consumer_honesty", "partner_fairness", "workplace_culture"):
        assert key in FOODSERVICE_FRANCHISE.obligations


def test_exec_conduct_is_catastrophic_and_ethics_exposed():
    g = build_obligation_graph(FOODSERVICE_FRANCHISE)
    root = g.get("obl:exec_conduct:exec_conduct")
    assert root.severity == CATASTROPHIC       # gapjil ends CEOs
    assert "윤리·품행" in root.exposure


def test_every_category_maps_to_real_cases():
    for cat in RISK_CATEGORIES:
        assert isinstance(cat, RiskCategory)
        assert cat.cases  # each category is grounded in at least one real ousting


def test_coverage_reports_categories_now_covered():
    all_keys = {k for v in VERTICALS.values() for k in v.obligations}
    status = {cat.code: st for cat, st in coverage(all_keys)}
    # the four gaps the survey revealed are now covered
    assert status["C4"].startswith("✓")   # 오너·임원 품행
    assert status["C5"].startswith("✓")   # 파트너 갑질
    assert status["C3"].startswith("✓")   # 소비자 기만


def test_gapjil_control_surfaces_in_register():
    g = ground(build_obligation_graph(FOODSERVICE_FRANCHISE), Evidence())
    ids = {i.contract_id for i in risk_register(g)}
    assert "obl:exec_conduct:gapjil_monitoring" in ids
    assert "obl:partner_fairness:no_forced_supply" in ids


def test_exposure_weight_includes_ethics():
    from selfdeploy.ir import EXPOSURE_WEIGHT

    assert EXPOSURE_WEIGHT["윤리·품행"] == 0.9
