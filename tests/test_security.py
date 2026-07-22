"""Local-first, enforced: the deterministic core runs with the network BLOCKED,
LLM paths raise loudly, portfolios encrypt at rest, and the UI binds loopback only."""
import json
import socket
import urllib.request

import pytest

from selfdeploy import (
    Portfolio,
    ask,
    build_obligation_graph,
    ground,
    load_portfolio,
    management_surface,
    risk_register,
    save_portfolio,
    select,
    track,
)
from selfdeploy.grounding import Evidence, Signal
from selfdeploy.security import (
    NetworkBlockedError,
    decrypt_json,
    encrypt_json,
    is_encrypted_file,
    offline_guard,
)
from selfdeploy.templates import FOODSERVICE_FRANCHISE, INJECTION_MOLDING


# --- guarantee 1: the deterministic core needs no network -------------------- #

def test_core_pipeline_runs_fully_offline(tmp_path):
    with offline_guard():
        ev = Evidence(signals=[Signal(id="ERP.sales", kind="data", tags=["sales_ledger"])])
        # grounding + register
        g = ground(build_obligation_graph(INJECTION_MOLDING), ev)
        assert risk_register(g)
        # the ask door
        r = ask("제품별 마진 알고 싶다", INJECTION_MOLDING, ev, at="2026-07-08")
        assert r.resolutions
        # management surface + selection + tracking + persistence
        surface = management_surface(FOODSERVICE_FRANCHISE, ev)
        pf = Portfolio(vertical=FOODSERVICE_FRANCHISE.name)
        track(pf, select(surface, top=3), at="2026-07-08")
        save_portfolio(pf, tmp_path / "pf.json")
        assert load_portfolio(tmp_path / "pf.json").items


def test_offline_guard_blocks_sockets():
    with offline_guard():
        with pytest.raises(NetworkBlockedError):
            socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        with pytest.raises(NetworkBlockedError):
            socket.getaddrinfo("api.anthropic.com", 443)
    # and restores afterwards
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.close()


def test_llm_path_raises_inside_offline():
    from selfdeploy.llm import ClaudeDesireMapper

    with offline_guard():
        with pytest.raises(Exception):  # anthropic client cannot open a connection
            ClaudeDesireMapper().map_desire("아무 욕구", INJECTION_MOLDING)


# --- guarantee 4: at-rest encryption ----------------------------------------- #

def test_encrypt_roundtrip_and_wrong_passphrase():
    env = encrypt_json({"secret": "임원 비위 내역"}, "correct horse")
    assert "임원 비위" not in env                      # ciphertext, not plaintext
    assert decrypt_json(env, "correct horse")["secret"] == "임원 비위 내역"
    with pytest.raises(Exception):
        decrypt_json(env, "wrong passphrase")


def test_portfolio_encrypted_at_rest(tmp_path):
    surface = management_surface(FOODSERVICE_FRANCHISE, Evidence())
    pf = Portfolio(vertical=FOODSERVICE_FRANCHISE.name)
    track(pf, select(surface, codes={"C4"}), at="2026-07-01")
    path = tmp_path / "pf.enc.json"
    save_portfolio(pf, path, passphrase="s3cret")
    raw = path.read_text(encoding="utf-8")
    assert is_encrypted_file(path)
    assert "갑질" not in raw                           # sensitive labels not in plaintext
    loaded = load_portfolio(path, passphrase="s3cret")
    assert set(loaded.items) == set(pf.items)
    with pytest.raises(ValueError):
        load_portfolio(path)                           # passphrase required


# --- guarantee 3 + UI: serve binds loopback and answers ----------------------- #

def test_serve_is_loopback_only_and_functional():
    from selfdeploy.server import serve
    import threading

    ev = Evidence(signals=[Signal(id="ERP.sales", kind="data", tags=["sales_ledger"])])
    httpd = serve(FOODSERVICE_FRANCHISE, ev, port=0)   # ephemeral port
    host, port = httpd.server_address[:2]
    assert host == "127.0.0.1"                         # enforced by construction
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        page = urllib.request.urlopen(f"http://127.0.0.1:{port}/").read().decode()
        assert "무엇이 궁금하세요" in page and "127.0.0.1" in page
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/ask",
            data=json.dumps({"desire": "매출 성장 어떻게 되고 있나"}).encode(),
            headers={"Content-Type": "application/json"},
        )
        j = json.loads(urllib.request.urlopen(req).read())
        assert "verdict" in j and (j["answered"] or j["routed"])
        brief = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/api/brief").read())
        assert len(brief["items"]) == 3
        assert brief["items"][0]["why"]                # rationale attached
    finally:
        httpd.shutdown()
        httpd.server_close()


# --- ② LLM desire mapper: gated ----------------------------------------------- #

def test_desire_mapper_gate_and_ask_integration():
    from types import SimpleNamespace

    from selfdeploy.llm import ClaudeDesireMapper

    fake = SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: SimpleNamespace(
        content=[SimpleNamespace(type="text",
                 text='{"kpi_keys":["profitability","fake_kpi"],"obligation_keys":["exec_conduct"]}')])))
    mapper = ClaudeDesireMapper(client=fake)
    kpis, obls = mapper.map_desire("수익도 갑질도 궁금", FOODSERVICE_FRANCHISE)
    assert kpis == ["profitability"] and obls == ["exec_conduct"]  # fake_kpi gated out

    r = ask("아무 표현", FOODSERVICE_FRANCHISE, Evidence(), at="2026-07-08", mapper=mapper)
    assert "profitability" in r.matched and "exec_conduct" in r.matched
