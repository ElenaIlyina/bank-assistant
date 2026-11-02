from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    db_pool_min: int = 1
    db_pool_max: int = 10

    llm_base_url: str = "http://localhost:1234/v1"
    llm_api_key: str = "lm-studio"
    llm_model: str = "gemma-4-e4b-it"
    llm_timeout_s: float = 120.0
    llm_max_retries: int = 3
    agent_max_turns: int = 6
    agent_timeout_s: float = 300.0
    confidence_threshold: float = Field(default=0.6, ge=0, le=1)

    temporal_host: str = "localhost:7233"
    temporal_task_queue: str = "mortgage"
    temporal_activity_threads: int = Field(default=4, ge=1)

    embedding_model: str = "google/embeddinggemma-300m"
    embedding_batch_size: int = Field(default=8, ge=1)

    search_similarity_threshold: float = Field(default=0.30, ge=-1, le=1)

settings = Settings()
