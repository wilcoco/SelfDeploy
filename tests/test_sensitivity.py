"""The 탱크데이 archetype: outbound-decision sensitivity, not an operational record."""
from types import SimpleNamespace

from selfdeploy import build_obligation_graph, by_exposure, by_regulation, check_campaign, ground, risk_register
from selfdeploy.grounding import Evidence
from selfdeploy.sensitivity import LLMSensitivityChecker
from selfdeploy.templates import FOODSERVICE_FRANCHISE


def test_would_have_caught_the_real_tankday():
    # the actual campaign: name "탱크데이", copy "책상에 탁!", launched 2026-05-18
    flags = check_campaign("탱크데이 이벤트 — 책상에 탁!", date="2026-05-18")
    reasons = " ".join(f.reason for f in flags)
    assert "5·18" in reasons          # date collision
    assert "박종철" in reasons         # '책상을 탁' phrase
    assert "계엄군" in reasons         # '탱크' phrase
    assert len(flags) >= 3


def test_same_copy_safe_date_still_flags_phrases():
    flags = check_campaign("탱크데이 — 책상에 탁!", date="2026-07-01")
    kinds = {f.kind for f in flags}
    assert "phrase" in kinds and "date" not in kinds


def test_clean_campaign_no_flags():
    assert check_campaign("여름 시즌 신메뉴 출시 이벤트", date="2026-07-01") == []


def test_accepts_month_day_form():
    flags = check_campaign("광복 기념 행사", date="08-15")
    assert any(f.kind == "date" for f in flags)


def test_llm_pass_adds_flags():
    fake = SimpleNamespace(
        messages=SimpleNamespace(
            create=lambda **kw: SimpleNamespace(
                content=[SimpleNamespace(
                    type="text",
                    text='{"collisions":[{"matched":"특정표현","reason":"신종 정치 민감성"}]}',
                )]
            )
        )
    )
    flags = check_campaign("무난한 문구", date="2026-07-01", llm=LLMSensitivityChecker(client=fake))
    assert any(f.kind == "llm" and "신종" in f.reason for f in flags)


# --- the obligation side ---------------------------------------------------- #

def test_brand_sensitivity_obligation_present_and_catastrophic():
    g = build_obligation_graph(FOODSERVICE_FRANCHISE)
    root = g.get("obl:brand_sensitivity:brand_sensitivity")
    assert root.severity == 1.0                       # CATASTROPHIC — it fired a CEO
    assert "역사·사회" in root.exposure


def test_brand_sensitivity_is_invisible_to_a_legal_view():
    g = ground(build_obligation_graph(FOODSERVICE_FRANCHISE), Evidence())
    reg = risk_register(g)
    brand_ids = {i.contract_id for i in reg if i.contract_id.startswith("obl:brand_sensitivity")}
    # a legal (by_regulation) rollup never surfaces these — they carry no law
    by_law_ids = {i.contract_id for _law, items in by_regulation(reg) for i in items}
    assert brand_ids and not (brand_ids & by_law_ids)
    # but the exposure rollup surfaces them under 역사·사회
    by_hist = {i.contract_id for cls, items in by_exposure(reg) if cls == "역사·사회" for i in items}
    assert brand_ids <= by_hist
