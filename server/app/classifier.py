"""Claude 기반 실시간 이슈 분류.

들어온 메시지 한 건을 카테고리/긴급도로 분류한다. 단일 LLM 호출 + 구조화 출력
(output_config.format)으로 항상 유효한 JSON 을 받는다.
"""

import json

from .config import get_settings
from .llm import get_client

CATEGORIES = ["incident", "request", "question", "decision", "info", "chitchat"]
LEVELS = ["urgent", "normal", "low"]

_SCHEMA = {
    "type": "object",
    "properties": {
        "category": {
            "type": "string",
            "enum": CATEGORIES,
            "description": (
                "incident=장애/사고, request=업무요청, question=질문, "
                "decision=의사결정/합의, info=공지/정보공유, chitchat=잡담"
            ),
        },
        "level": {
            "type": "string",
            "enum": LEVELS,
            "description": "urgent=즉시 대응 필요, normal=일반 업무, low=참고/잡담",
        },
        "summary": {"type": "string", "description": "한 줄 한국어 요약(40자 이내)"},
        "confidence": {"type": "number", "description": "0.0~1.0 확신도"},
    },
    "required": ["category", "level", "summary", "confidence"],
    "additionalProperties": False,
}

_SYSTEM = (
    "너는 회사 업무용 단톡방 메시지를 분류하는 시스템이다. "
    "각 메시지를 카테고리와 긴급도로 분류하고 한 줄 요약하라. "
    "장애/오류/긴급/다운/먹통/안됨 등 운영 위험 신호는 incident+urgent 로 분류하라. "
    "반드시 한국어로 요약한다."
)


def classify(room: str, sender: str, masked_text: str) -> dict:
    settings = get_settings()
    client = get_client()

    resp = client.messages.create(
        model=settings.classifier_model,
        max_tokens=512,
        system=_SYSTEM,
        output_config={"format": {"type": "json_schema", "schema": _SCHEMA}},
        messages=[
            {
                "role": "user",
                "content": f"[방] {room}\n[발신자] {sender}\n[메시지] {masked_text}",
            }
        ],
    )

    text = next((b.text for b in resp.content if b.type == "text"), "{}")
    data = json.loads(text)
    # 방어적 기본값
    data.setdefault("category", "info")
    data.setdefault("level", "normal")
    data.setdefault("summary", masked_text[:40])
    data.setdefault("confidence", 0.0)
    return data
