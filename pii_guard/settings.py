from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PII_",
        env_file=".env",
        extra="ignore",
    )

    redis_url: str | None = None
    mapping_ttl_seconds: int = 1800
    encryption_key: SecretStr | None = None
    hmac_key: SecretStr | None = None
    max_body_bytes: int = 4_000_000
    log_level: str = "INFO"
    config_dir: Path = Path("config")
    recognizer_modules: list[str] = [
        "pii_guard.recognizers.numeric",
        "pii_guard.recognizers.documents",
        "pii_guard.recognizers.dates",
        "pii_guard.recognizers.names",
        "pii_guard.recognizers.address",
    ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
