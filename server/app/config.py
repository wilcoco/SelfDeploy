from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str = ""
    ingest_token: str = "change-me"
    database_url: str = "sqlite:///./selfdeploy.db"

    classifier_model: str = "claude-opus-4-8"
    answer_model: str = "claude-opus-4-8"

    # 콤마 구분 문자열 → 집합으로 노출
    alert_levels: str = "urgent,incident"

    @property
    def alert_level_set(self) -> set[str]:
        return {s.strip() for s in self.alert_levels.split(",") if s.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
