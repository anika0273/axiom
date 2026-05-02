"""Application settings loaded once at startup from environment variables.

All environment access happens here. No other module may read os.environ directly.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Axiom runtime configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Application ───────────────────────────────────────────────────────────
    ENVIRONMENT: str = "development"
    SECRET_KEY: str = "dev-secret-change-in-prod"
    DEBUG: bool = True

    # ── Database ──────────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://axiom:changeme@localhost:5432/axiom"

    # ── Individual Postgres vars (used by docker-compose) ─────────────────────
    POSTGRES_USER: str = "axiom"
    POSTGRES_PASSWORD: str = "changeme"
    POSTGRES_DB: str = "axiom"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432

    # ── AI ────────────────────────────────────────────────────────────────────
    ANTHROPIC_API_KEY: str = ""

    # ── CORS ──────────────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: str = "http://localhost:5173"


settings = Settings()
