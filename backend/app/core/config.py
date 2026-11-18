"""Central configuration loaded from environment variables (never hard-code secrets)."""
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_ENV: str = "development"
    APP_NAME: str = "AI_FinanceMate"
    LOG_LEVEL: str = "INFO"

    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "openai/gpt-oss-120b"
    GROQ_TIMEOUT_SECONDS: float = 30.0
    GROQ_MAX_RETRIES: int = 2

    DATABASE_URL: str = "postgresql+psycopg://postgres@localhost:5432/financemate"
    TEST_DATABASE_URL: str = "postgresql+psycopg://postgres@localhost:5432/financemate_test"

    JWT_SECRET_KEY: str = Field(default="", min_length=0)
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    FRONTEND_URL: str = "http://localhost:5173"
    CORS_ORIGINS: str = "http://localhost:5173"
    MAX_UPLOAD_SIZE_MB: int = 10
    RATE_LIMIT_DEFAULT: str = "120/minute"

    AGENT_MAX_ITERATIONS: int = 5
    ASSISTANT_CONFIRM_CREATES: bool = True
    CONFIRMATION_TTL_MINUTES: int = 15

    @field_validator("DATABASE_URL", "TEST_DATABASE_URL")
    @classmethod
    def _normalize_driver(cls, v: str) -> str:
        # Hosting providers hand out postgres:// or postgresql:// URLs; force the psycopg3 driver.
        if v.startswith("postgres://"):
            v = "postgresql://" + v[len("postgres://"):]
        if v.startswith("postgresql://"):
            v = "postgresql+psycopg://" + v[len("postgresql://"):]
        return v

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        origins = [o.strip().rstrip("/") for o in self.CORS_ORIGINS.split(",") if o.strip()]
        if self.FRONTEND_URL and self.FRONTEND_URL.rstrip("/") not in origins:
            origins.append(self.FRONTEND_URL.rstrip("/"))
        return origins

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    @property
    def llm_configured(self) -> bool:
        return bool(self.GROQ_API_KEY and self.GROQ_MODEL)


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if not s.JWT_SECRET_KEY or len(s.JWT_SECRET_KEY) < 32:
        if s.is_production:
            raise RuntimeError("JWT_SECRET_KEY must be set (>=32 chars) in production")
        # Development convenience only: ephemeral secret, tokens reset on restart.
        import secrets

        s.JWT_SECRET_KEY = secrets.token_urlsafe(48)
    return s


settings = get_settings()
