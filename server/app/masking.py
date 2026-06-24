"""개인정보 마스킹.

수집 단계에서 본문의 민감정보를 정규식으로 치환한다. 저장 전에 반드시 적용한다.
한국 환경에 맞춰 전화/주민/계좌/카드/이메일을 우선 처리하며, 이름은 발신자명 기반으로
부분 마스킹한다. (NER 기반 정밀 마스킹은 운영 단계에서 추가 가능)
"""

import re

# 주민등록번호: 6자리-7자리
RRN = re.compile(r"\b\d{6}[-\s]?[1-4]\d{6}\b")
# 휴대폰/전화: 010-1234-5678, 02-123-4567 등
PHONE = re.compile(r"\b0\d{1,2}[-\s.]?\d{3,4}[-\s.]?\d{4}\b")
# 카드번호: 4-4-4-4
CARD = re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b")
# 계좌번호: 숫자(-) 조합 9자리 이상 (카드/전화와 겹치지 않도록 뒤에 처리)
ACCOUNT = re.compile(r"\b\d{2,6}[-\s]\d{2,6}[-\s]\d{2,7}(?:[-\s]\d{1,6})?\b")
# 이메일
EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")


def _mask_keep_edges(token: str, keep: int = 0) -> str:
    digits = re.sub(r"\D", "", token)
    return "*" * len(digits) if len(digits) <= keep else token


def mask_pii(text: str) -> str:
    """본문에서 개인정보를 마스킹한 문자열을 반환한다."""
    if not text:
        return text

    text = RRN.sub("[주민번호]", text)
    text = CARD.sub("[카드번호]", text)
    text = EMAIL.sub("[이메일]", text)
    # 전화는 마지막 4자리만 남기고 마스킹
    text = PHONE.sub(lambda m: _mask_phone(m.group()), text)
    # 계좌 패턴은 전화/카드 치환 후 남은 것만
    text = ACCOUNT.sub("[계좌번호]", text)
    return text


def _mask_phone(token: str) -> str:
    digits = re.sub(r"\D", "", token)
    if len(digits) < 4:
        return "[전화번호]"
    return "[전화]-****-" + digits[-4:]


def mask_name(name: str) -> str:
    """발신자 이름 부분 마스킹: 홍길동 → 홍*동, 김철 → 김*."""
    name = (name or "").strip()
    if len(name) <= 1:
        return name or "익명"
    if len(name) == 2:
        return name[0] + "*"
    return name[0] + "*" * (len(name) - 2) + name[-1]
