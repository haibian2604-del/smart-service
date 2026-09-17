from decimal import Decimal
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://postgres:123456@127.0.0.1:5432/smart_service"
    test_database_url: str = "postgresql+asyncpg://postgres:123456@127.0.0.1:5432/smart_service_test"
    llm_base_url: str = "http://127.0.0.1:8080/v1"
    llm_model: str = "gemma-4-e2b-it-4bit"
    llm_api_key: str = "none"
    refund_amount_threshold: Decimal = Decimal("200")


@lru_cache
def get_settings() -> Settings:
    return Settings()
