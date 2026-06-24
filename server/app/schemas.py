from datetime import datetime

from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    room: str = Field(..., description="단톡방 이름")
    sender: str = Field(..., description="발신자(원본 이름; 서버에서 마스킹됨)")
    text: str = Field(..., description="메시지 본문(원본; 서버에서 마스킹됨)")
    ts: datetime | None = Field(None, description="발신 시각(ISO8601). 없으면 수신 시각 사용")


class IssueOut(BaseModel):
    category: str
    level: str
    summary: str
    confidence: float


class IngestResponse(BaseModel):
    message_id: int
    masked_text: str
    issue: IssueOut
    alerted: bool


class AskRequest(BaseModel):
    question: str
    room: str | None = Field(None, description="특정 방으로 한정(선택)")
    hours: int = Field(72, description="검색 시간 범위(시간)")


class AskResponse(BaseModel):
    answer: str
    sources: list[str]


class IssueListItem(BaseModel):
    message_id: int
    room: str
    sender: str
    text: str
    category: str
    level: str
    summary: str
    sent_at: datetime
