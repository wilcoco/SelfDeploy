"""수집 파이프라인: 마스킹 → 저장 → 분류 → (긴급시) 알림."""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from . import classifier
from .config import get_settings
from .masking import mask_name, mask_pii
from .models import IssueClassification, Message
from .schemas import IngestRequest

logger = logging.getLogger("selfdeploy.ingest")


def ingest_message(db: Session, req: IngestRequest) -> tuple[Message, IssueClassification, bool]:
    settings = get_settings()

    masked_text = mask_pii(req.text)
    masked_sender = mask_name(req.sender)
    sent_at = req.ts or datetime.now(timezone.utc)

    msg = Message(
        room=req.room,
        sender=masked_sender,
        text=masked_text,
        sent_at=sent_at,
    )
    db.add(msg)
    db.flush()  # msg.id 확보

    result = classifier.classify(req.room, masked_sender, masked_text)
    issue = IssueClassification(
        message_id=msg.id,
        category=result["category"],
        level=result["level"],
        summary=result["summary"],
        confidence=float(result["confidence"]),
    )
    db.add(issue)
    db.commit()

    alerted = issue.level in settings.alert_level_set
    if alerted:
        _send_alert(msg, issue)

    return msg, issue, alerted


def _send_alert(msg: Message, issue: IssueClassification) -> None:
    """긴급 이슈 알림 훅. 운영시 메일/Slack/카카오 알림톡 등으로 교체.

    지금은 로그로만 남긴다.
    """
    logger.warning(
        "🚨 긴급 이슈 감지 [%s/%s] (%s) %s: %s",
        issue.category,
        issue.level,
        msg.room,
        msg.sender,
        issue.summary,
    )
