from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Message(Base):
    """단톡방에서 수집한 메시지 한 건. text 는 마스킹된 본문만 저장한다."""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    room: Mapped[str] = mapped_column(String(255), index=True)
    sender: Mapped[str] = mapped_column(String(255))
    text: Mapped[str] = mapped_column(Text)  # 마스킹 완료된 본문
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    issue: Mapped["IssueClassification | None"] = relationship(
        back_populates="message", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_messages_room_sent_at", "room", "sent_at"),)


class IssueClassification(Base):
    """메시지에 대한 실시간 이슈 분류 결과."""

    __tablename__ = "issue_classifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    message_id: Mapped[int] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), index=True
    )
    category: Mapped[str] = mapped_column(String(32), index=True)  # incident/request/...
    level: Mapped[str] = mapped_column(String(16), index=True)  # urgent/normal/low
    summary: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )

    message: Mapped[Message] = relationship(back_populates="issue")
