"""Optional LLM requirement->KPI mapper — the one isolated nondeterminism stage.

This is the *only* place nondeterminism may enter the pipeline, and it is fenced
by a deterministic gate: the mapper chooses among the vertical's *known* KPI keys
and nothing else; build_graph then instantiates only those templates, and any
intent that maps to nothing becomes a RED unknown cell. The LLM routes; it never
invents structure. Same thesis: isolate the probabilistic step, harden the gate
around it.

Off by default. The CLI uses deterministic keyword matching unless --llm is
passed. Requires the `anthropic` package and credentials; the import is lazy so
the rest of the package runs with neither installed.
"""
from __future__ import annotations

import json

from .templates import VerticalTemplate

DEFAULT_MODEL = "claude-opus-4-8"

_SYSTEM = (
    "You route a manufacturing manager's (often vague) requirement onto a fixed "
    "set of known KPI keys. Choose only from the provided keys. If the requirement "
    "implies none of them, return an empty list. You never invent KPIs and you do "
    "not design structure — this is a routing decision; the downstream system owns "
    "the entailment structure and the grounding."
)


class ClaudeRequirementMapper:
    """Maps a requirement to known KPI keys via Claude, with a deterministic gate."""

    def __init__(self, model: str = DEFAULT_MODEL, client=None):
        self.model = model
        self._client = client

    def _client_or_default(self):
        if self._client is None:
            import anthropic  # lazy — keeps `anthropic` an optional dependency

            self._client = anthropic.Anthropic()
        return self._client

    def map(self, requirement_text: str, vertical: VerticalTemplate) -> list[str]:
        keys = list(vertical.kpis)
        catalog = "\n".join(f"- {k}: {vertical.kpis[k].label}" for k in keys)
        client = self._client_or_default()

        response = client.messages.create(
            model=self.model,
            max_tokens=2048,
            thinking={"type": "adaptive"},
            system=_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"업종: {vertical.name}\n\n"
                        f"알려진 KPI 키:\n{catalog}\n\n"
                        f"경영자 요구사항:\n{requirement_text}\n\n"
                        "이 요구가 매핑되는 KPI 키만 고르라."
                    ),
                }
            ],
            output_config={
                "format": {
                    "type": "json_schema",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "kpi_keys": {
                                "type": "array",
                                "items": {"type": "string", "enum": keys},
                            }
                        },
                        "required": ["kpi_keys"],
                        "additionalProperties": False,
                    },
                }
            },
        )

        text = next((b.text for b in response.content if b.type == "text"), "{}")
        chosen = set(json.loads(text).get("kpi_keys", []))
        # Deterministic gate: keep only known keys, dedupe, preserve template order.
        return [k for k in keys if k in chosen]


class ClaudeDesireMapper:
    """Maps a CEO's natural-language desire onto known KPI *and* obligation keys.

    The `ask` door's robust matcher: the keyword fallback is fragile in Korean
    (substring collisions like 출하⊂진출하); this asks Claude, but stays fenced —
    the model may only choose among the vertical's known keys, and the output is
    filtered back to those keys. It routes; it never invents structure.
    """

    def __init__(self, model: str = DEFAULT_MODEL, client=None):
        self.model = model
        self._client = client

    def _client_or_default(self):
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic()
        return self._client

    def map_desire(self, desire: str, vertical) -> tuple[list[str], list[str]]:
        kpi_keys = list(vertical.kpis)
        obl_keys = list(vertical.obligations)
        catalog = "\n".join(
            [f"- KPI {k}: {vertical.kpis[k].label}" for k in kpi_keys]
            + [f"- 의무 {k}: {vertical.obligations[k].label}" for k in obl_keys]
        )
        client = self._client_or_default()
        response = client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=(
                "You route a CEO's natural-language desire (a risk worry OR an "
                "opportunity ask) onto known KPI keys and obligation keys. Choose "
                "only from the provided keys; if nothing fits, return empty lists. "
                "You never invent keys — routing only."
            ),
            messages=[{
                "role": "user",
                "content": (
                    f"업종: {vertical.name}\n\n알려진 키:\n{catalog}\n\n"
                    f"대표의 욕구:\n{desire}\n\n이 욕구가 매핑되는 키만 고르라."
                ),
            }],
            output_config={
                "format": {
                    "type": "json_schema",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "kpi_keys": {"type": "array", "items": {"type": "string", "enum": kpi_keys or ["__none__"]}},
                            "obligation_keys": {"type": "array", "items": {"type": "string", "enum": obl_keys or ["__none__"]}},
                        },
                        "required": ["kpi_keys", "obligation_keys"],
                        "additionalProperties": False,
                    },
                }
            },
        )
        import json as _json

        text = next((b.text for b in response.content if b.type == "text"), "{}")
        data = _json.loads(text)
        # deterministic gate: known keys only, template order, deduped
        kpis = [k for k in kpi_keys if k in set(data.get("kpi_keys", []))]
        obls = [k for k in obl_keys if k in set(data.get("obligation_keys", []))]
        return kpis, obls
