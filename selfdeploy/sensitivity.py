"""Pre-release sensitivity checking — the 탱크데이 archetype.

Some CEO-ending risks are not a missing operational record; they are an outbound,
irreversible decision — a campaign name, a launch date, ad copy — that collides
with a historical, political, or social sensitivity. The control is a *pre-release
review gate*, and this module is the check that gate should run: given campaign
text + a launch date, flag collisions with known sensitive dates and phrases.

The 탱크데이 case (2026-05-18, "탱크데이 / 책상에 탁!") collides on BOTH the date
(5·18 광주 민주화운동) and the phrasing (박종철 '책상을 탁', 탱크=계엄군). This
check flags all three — a legal-compliance view would have caught none of them,
because the law (5·18 특별법·명예훼손) only followed the public outrage.

Deterministic seed catalog (below) + an optional LLM pass for novel collisions
the seed can't enumerate. The seed alone fully catches 탱크데이.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# month-day (MM-DD) -> sensitive anniversary. A launch on one of these is a landmine.
SENSITIVE_DATES: dict[str, str] = {
    "05-18": "5·18 광주 민주화운동",
    "06-10": "6·10 민주항쟁",
    "04-03": "제주 4·3 사건",
    "04-16": "세월호 참사",
    "03-01": "3·1 운동",
    "08-15": "광복절",
    "11-03": "학생독립운동기념일",
    "12-12": "12·12 군사반란",
}

# (regex, why it is sensitive) — phrasing that evokes trauma/atrocity/oppression.
SENSITIVE_PHRASES: list[tuple[str, str]] = [
    (r"책상.{0,4}(탁|툭)", "박종철 고문치사 '책상을 탁 치니 억' 연상"),
    (r"탱크|장갑차|계엄", "5·18 계엄군 무력진압 연상"),
    (r"고문|물고문", "인권침해·고문 연상"),
    (r"위안부|정신대", "일본군 위안부 — 극도 민감"),
    (r"세월호|기울(어|은)?\s*배", "세월호 참사 연상"),
    (r"학살|양민", "민간인 학살 연상"),
]


@dataclass
class Flag:
    kind: str      # "date" | "phrase" | "llm"
    matched: str
    reason: str


def _norm_md(date: str) -> str:
    return date[-5:] if len(date) >= 5 else date  # accept YYYY-MM-DD or MM-DD


def check_campaign(text: str, date: str | None = None, llm=None) -> list[Flag]:
    """Flag a proposed campaign's collisions with sensitive dates/phrases."""
    flags: list[Flag] = []
    if date:
        md = _norm_md(date)
        if md in SENSITIVE_DATES:
            flags.append(Flag("date", date, f"출시일이 {SENSITIVE_DATES[md]}와 충돌"))
    for pattern, reason in SENSITIVE_PHRASES:
        m = re.search(pattern, text)
        if m:
            flags.append(Flag("phrase", m.group(0), reason))
    if llm is not None:
        flags.extend(llm.check(text, date))
    return flags


class LLMSensitivityChecker:
    """Optional LLM pass for collisions the seed catalog can't enumerate.

    Historical/political/cultural sensitivities are open-ended; a fixed regex list
    can't cover every one. This asks a model for additional collisions, returned as
    Flags. Offline-safe (lazy import, injectable client). It *adds* to the
    deterministic flags, never replaces them.
    """

    def __init__(self, client=None, model: str | None = None):
        from .llm import DEFAULT_MODEL

        self.model = model or DEFAULT_MODEL
        self._client = client

    def _client_or_default(self):
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic()
        return self._client

    def check(self, text: str, date: str | None) -> list[Flag]:
        import json

        client = self._client_or_default()
        response = client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=(
                "You screen a marketing campaign for collisions with historical, "
                "political, or social sensitivities (especially Korean context: "
                "민주화운동, 참사, 인권, 노동, 젠더). Return only genuine collisions."
            ),
            messages=[
                {
                    "role": "user",
                    "content": f"캠페인 문구: {text}\n출시일: {date or '(미정)'}\n민감성 충돌을 찾아라.",
                }
            ],
            output_config={
                "format": {
                    "type": "json_schema",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "collisions": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "matched": {"type": "string"},
                                        "reason": {"type": "string"},
                                    },
                                    "required": ["matched", "reason"],
                                    "additionalProperties": False,
                                },
                            }
                        },
                        "required": ["collisions"],
                        "additionalProperties": False,
                    },
                }
            },
        )
        text_out = next((b.text for b in response.content if b.type == "text"), '{"collisions": []}')
        return [Flag("llm", c["matched"], c["reason"]) for c in json.loads(text_out).get("collisions", [])]
