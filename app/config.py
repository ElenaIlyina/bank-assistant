"""Application settings loaded strictly from environment.

Missing required env var must prevent startup (criterias.txt), so defaults are forbidden.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str
    temporal_host: str


def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


@lru_cache
def settings() -> Settings:
    return get_settings()
