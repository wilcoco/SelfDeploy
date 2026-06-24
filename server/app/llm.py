"""Anthropic 클라이언트 싱글턴."""

from functools import lru_cache

import anthropic

from .config import get_settings


@lru_cache
def get_client() -> anthropic.Anthropic:
    settings = get_settings()
    # api_key 미설정 시 환경변수(ANTHROPIC_API_KEY)에서 자동 로드
    if settings.anthropic_api_key:
        return anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return anthropic.Anthropic()
