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
