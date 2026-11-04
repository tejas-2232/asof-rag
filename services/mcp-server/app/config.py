from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    sec_user_agent: str = ""
    qdrant_url: str = "http://localhost:6333"
    data_dir: Path = Path("./data")
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    cors_origins: str = "http://localhost:3000,http://localhost:5173"
    sec_cache_ttl_seconds: int = 86_400
    sec_request_interval_seconds: float = 0.12
    sec_max_retries: int = 4

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return settings
