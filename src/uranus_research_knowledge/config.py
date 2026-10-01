from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="KNOWLEDGE_", extra="forbid", env_file=None, hide_input_in_errors=True
    )
    api_key: SecretStr
    encoder_url: str = "http://127.0.0.1:6335"
    encoder_api_key: SecretStr
    qdrant_url: str = "http://127.0.0.1:6333"
    qdrant_api_key: SecretStr
    timeout_seconds: float = Field(default=15, ge=1, le=60)
    concurrency: int = Field(default=4, ge=1, le=16)

    @field_validator("api_key", "encoder_api_key", "qdrant_api_key")
    @classmethod
    def key(cls, value: SecretStr) -> SecretStr:
        raw = value.get_secret_value()
        if not 32 <= len(raw) <= 4096 or any(not 33 <= ord(c) <= 126 for c in raw):
            raise ValueError("invalid_service_key")
        return value

    @field_validator("encoder_url", "qdrant_url")
    @classmethod
    def origin(cls, value: str) -> str:
        p = urlsplit(value)
        if (
            p.scheme not in {"http", "https"}
            or not p.hostname
            or p.username
            or p.password
            or p.path not in {"", "/"}
            or p.query
            or p.fragment
        ):
            raise ValueError("invalid_service_origin")
        if p.scheme == "http" and p.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("remote_services_require_tls")
        return value.rstrip("/")
