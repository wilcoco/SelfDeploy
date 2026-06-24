"""RAG: 관련 메시지 검색 + Claude 요약 답변.

MVP 단계에서는 임베딩 없이 '키워드 겹침 + 최신성' 기반으로 후보 메시지를 추린 뒤
Claude 에게 근거로 넘겨 답변을 생성한다. (운영 단계에서 pgvector/Voyage 임베딩으로 교체 가능)
"""

import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .llm import get_client
from .models import Message

_TOKEN = re.compile(r"[0-9A-Za-z가-힣]+")
_STOP = {"오늘", "어제", "관련", "이슈", "있었어", "있어", "뭐", "무슨", "있나요"}


def _tokens(text: str) -> set[str]:
    return {t for t in _TOKEN.findall(text.lower()) if len(t) > 1 and t not in _STOP}


def retrieve(
    db: Session, question: str, room: str | None, hours: int, limit: int = 12
) -> list[Message]:
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    stmt = select(Message).where(Message.sent_at >= since)
    if room:
        stmt = stmt.where(Message.room == room)
    candidates = list(db.execute(stmt.order_by(Message.sent_at.desc()).limit(500)).scalars())

    q_tokens = _tokens(question)

    def score(m: Message) -> tuple[int, datetime]:
        overlap = len(_tokens(m.text) & q_tokens)
        return (overlap, m.sent_at)

    # 키워드 겹침 우선, 동점이면 최신순
    ranked = sorted(candidates, key=score, reverse=True)
    # 겹침이 0 이면 최신 메시지로 폴백
    hits = [m for m in ranked if score(m)[0] > 0][:limit]
    return hits or ranked[:limit]


def answer(db: Session, question: str, room: str | None, hours: int) -> tuple[str, list[str]]:
    settings = get_settings()
    msgs = retrieve(db, question, room, hours)

    if not msgs:
        return "해당 기간에 관련된 대화 기록이 없습니다.", []

    context_lines = []
    sources = []
    for m in sorted(msgs, key=lambda x: x.sent_at):
        line = f"[{m.sent_at:%m-%d %H:%M}] ({m.room}) {m.sender}: {m.text}"
        context_lines.append(line)
        sources.append(line)
    context = "\n".join(context_lines)

    client = get_client()
    resp = client.messages.create(
        model=settings.answer_model,
        max_tokens=1024,
        system=(
            "너는 회사 단톡방 대화 기록을 근거로 질문에 답하는 어시스턴트다. "
            "아래 대화 기록만을 근거로 한국어로 간결하게 답하라. "
            "기록에 없는 내용은 추측하지 말고 '기록에 없음'이라고 답하라."
        ),
        messages=[
            {
                "role": "user",
                "content": f"[대화 기록]\n{context}\n\n[질문]\n{question}",
            }
        ],
    )
    text = next((b.text for b in resp.content if b.type == "text"), "")
    return text, sources
