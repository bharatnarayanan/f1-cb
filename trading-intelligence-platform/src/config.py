"""Runtime settings for the Trading Intelligence Platform, loaded from
environment variables.

Per docs/CLAUDE.md: fail loudly on a missing required setting rather than
falling back to a silent default that would mask a misconfigured deploy.
KITE_API_KEY / KITE_ACCESS_TOKEN must only ever be provisioned with
read-only market-data scope — see docs/CLAUDE.md section 2.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # --- Core ---
    environment: str = Field(default="development", alias="ENVIRONMENT")
    secret_key: str = Field(..., alias="SECRET_KEY")

    # --- Database (TimescaleDB) ---
    database_url: str = Field(..., alias="DATABASE_URL")

    # --- Redis (live tick cache, rate limiting, alert dedup) ---
    redis_url: str = Field(default="redis://redis:6379/0", alias="REDIS_URL")

    # --- Auth ---
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=60, alias="ACCESS_TOKEN_EXPIRE_MINUTES")

    # --- Zerodha Kite Connect: READ-ONLY market data scope only. ---
    # Never populate these with an app registered for order-management
    # scope; this codebase has no order-placement code path to use it.
    kite_api_key: str | None = Field(default=None, alias="KITE_API_KEY")
    kite_access_token: str | None = Field(default=None, alias="KITE_ACCESS_TOKEN")

    # --- Data source mode: "sample" (default, no Kite creds needed — an
    # in-memory random-walk client) or "live" (real Zerodha Kite Connect,
    # requires kite_api_key/kite_access_token). Phase 2 ships defaulting to
    # sample so the stack is provable end-to-end before a daily Kite login
    # has been done. Every route using market data reports this back.
    # Literal (not str): a typo'd value must fail loudly at startup, not
    # silently fall through to the live-Kite branch in
    # src/market_data/factory.py. ---
    data_mode: Literal["sample", "live"] = Field(default="sample", alias="DATA_MODE")

    # --- Alerts ---
    telegram_bot_token: str | None = Field(default=None, alias="TELEGRAM_BOT_TOKEN")
    smtp_host: str | None = Field(default=None, alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_user: str | None = Field(default=None, alias="SMTP_USER")
    smtp_password: str | None = Field(default=None, alias="SMTP_PASSWORD")

    # --- LLM (rationale narration + strategy-marketplace extraction ONLY) ---
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")

    # --- Worker cadence ---
    pattern_scan_interval_seconds: int = Field(default=300, alias="PATTERN_SCAN_INTERVAL_SECONDS")

    # --- Risk guardrail defaults (per-user overrides live in risk_settings table) ---
    vix_normal_max: float = Field(default=15.0, alias="VIX_NORMAL_MAX")
    vix_elevated_max: float = Field(default=20.0, alias="VIX_ELEVATED_MAX")
    vix_high_max: float = Field(default=30.0, alias="VIX_HIGH_MAX")


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
