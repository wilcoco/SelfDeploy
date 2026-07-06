"""The LLM mapper is the isolated nondeterminism stage; its gate must be deterministic.

We inject a fake client so no network/credentials are needed — the point under test
is the gate (only known keys survive, template order preserved), not Claude itself.
"""
from types import SimpleNamespace

from selfdeploy.llm import ClaudeRequirementMapper
from selfdeploy.templates import INJECTION_MOLDING


class _FakeMessages:
    def __init__(self, payload):
        self._payload = payload

    def create(self, **kwargs):
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=self._payload)])


class _FakeClient:
    def __init__(self, payload):
        self.messages = _FakeMessages(payload)


def test_gate_keeps_only_known_keys():
    # model returns a hallucinated key alongside real ones — the gate drops it
    fake = _FakeClient('{"kpi_keys": ["downtime", "employee_morale", "defect_rate"]}')
    mapper = ClaudeRequirementMapper(client=fake)
    result = mapper.map("아무 요구", INJECTION_MOLDING)
    assert result == ["defect_rate", "downtime"]  # template order, unknown dropped


def test_gate_handles_empty_selection():
    fake = _FakeClient('{"kpi_keys": []}')
    mapper = ClaudeRequirementMapper(client=fake)
    assert mapper.map("복지 개선", INJECTION_MOLDING) == []


def test_gate_dedupes():
    fake = _FakeClient('{"kpi_keys": ["defect_rate", "defect_rate"]}')
    mapper = ClaudeRequirementMapper(client=fake)
    assert mapper.map("불량", INJECTION_MOLDING) == ["defect_rate"]
