"""
Centralized configuration via Pydantic Settings.
All env vars in one place — no scattered os.getenv() calls.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    app_name: str = "BlackRock Retirement Micro-Savings API"
    app_version: str = "1.0.0"
    debug: bool = False

    # Server
    host: str = "0.0.0.0"
    port: int = 5477
    workers: int = 16

    # Cache — L1 (in-process)
    l1_cache_maxsize: int = 4096
    cache_ttl_seconds: int = 60

    # Cache — L2 (Redis)
    redis_url: str = "redis://redis:6379/0"
    redis_pool_size: int = 50

    # Finance defaults
    retirement_age: int = 60
    nps_annual_rate: float = 0.0711
    index_annual_rate: float = 0.1449


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Singleton — parsed once, reused everywhere (zero cost after first call)."""
    return Settings()
