from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed application settings.

    ``canvas_api_token`` is a ``SecretStr`` so accidental logging and repr output
    cannot expose the credential. Persistent token encryption is provided by
    :class:`~app.core.security.TokenCipher`.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Canvas Academic OS"
    environment: Literal["development", "test", "production"] = "development"
    database_url: str = "sqlite:///./data/academic_os.db"

    canvas_base_url: str = "https://canvas.instructure.com/api/v1"
    canvas_api_token: SecretStr = SecretStr("")
    canvas_encryption_key: SecretStr | None = None

    canvas_request_timeout_seconds: float = 30.0
    canvas_max_retries: int = 3
    canvas_min_rate_limit_sleep_seconds: float = 0.25
    canvas_max_rate_limit_sleep_seconds: float = 8.0

    scheduler_enabled: bool = False
    ddl_alert_poll_interval_minutes: int = 15
    alert_webhook_url: str | None = None
    alert_webhook_kind: Literal["generic", "discord", "telegram"] = "generic"
    alert_email_to: str | None = None

    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: SecretStr | None = None
    llm_model: str = "gpt-4o-mini"
    llm_timeout_seconds: float = 60.0
    materials_root_dir: str = "./data/course_materials"

    @field_validator("canvas_base_url")
    @classmethod
    def normalize_canvas_base_url(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        if not normalized.startswith(("http://", "https://")):
            raise ValueError("CANVAS_BASE_URL must start with http:// or https://")
        return normalized

    @property
    def canvas_token_value(self) -> str:
        """Return the token only at the explicit boundary where it is needed."""

        return self.canvas_api_token.get_secret_value()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
