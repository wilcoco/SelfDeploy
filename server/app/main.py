import logging

from fastapi import Depends, FastAPI, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import ingest, rag
from .config import get_settings
from .db import get_db, init_db
from .models import IssueClassification, Message
from .schemas import (
    AskRequest,
    AskResponse,
    IngestRequest,
    IngestResponse,
    IssueListItem,
    IssueOut,
)

logging.basicConfig(level=logging.INFO)
app = FastAPI(title="SelfDeploy — 카카오톡 단톡방 AI 분석")


@app.on_event("startup")
def _startup() -> None:
    init_db()


def require_ingest_token(authorization: str = Header(default="")) -> None:
    """수집 엔드포인트 인증: Authorization: Bearer <INGEST_TOKEN>."""
    settings = get_settings()
    expected = f"Bearer {settings.ingest_token}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="invalid ingest token")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/ingest", response_model=IngestResponse)
def ingest_endpoint(
    req: IngestRequest,
    db: Session = Depends(get_db),
    _: None = Depends(require_ingest_token),
) -> IngestResponse:
    msg, issue, alerted = ingest.ingest_message(db, req)
    return IngestResponse(
        message_id=msg.id,
        masked_text=msg.text,
        issue=IssueOut(
            category=issue.category,
            level=issue.level,
            summary=issue.summary,
            confidence=issue.confidence,
        ),
        alerted=alerted,
    )


@app.post("/ask", response_model=AskResponse)
def ask_endpoint(req: AskRequest, db: Session = Depends(get_db)) -> AskResponse:
    text, sources = rag.answer(db, req.question, req.room, req.hours)
    return AskResponse(answer=text, sources=sources)


@app.get("/issues", response_model=list[IssueListItem])
def issues_endpoint(
    level: str | None = None,
    room: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
) -> list[IssueListItem]:
    stmt = select(Message, IssueClassification).join(
        IssueClassification, IssueClassification.message_id == Message.id
    )
    if level:
        stmt = stmt.where(IssueClassification.level == level)
    if room:
        stmt = stmt.where(Message.room == room)
    stmt = stmt.order_by(Message.sent_at.desc()).limit(limit)

    rows = db.execute(stmt).all()
    return [
        IssueListItem(
            message_id=m.id,
            room=m.room,
            sender=m.sender,
            text=m.text,
            category=i.category,
            level=i.level,
            summary=i.summary,
            sent_at=m.sent_at,
        )
        for m, i in rows
    ]
