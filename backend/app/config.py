"""Application settings, read once from the environment.

Nothing in here is a secret by default. Secrets (DB password, LLM API key)
arrive through environment variables injected by Compose (.env) or a
Kubernetes Secret — never from a file committed to the repository.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ProviderName = Literal["llm", "ollama", "rules", "simulated"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore", case_sensitive=False)

    app_name: str = "civicpulse"
    environment: str = "dev"
    log_level: str = "INFO"

    database_url: str = "postgresql+psycopg://civicpulse:civicpulse@postgres:5432/civicpulse"
    db_pool_size: int = 5
    redis_url: str = "redis://redis:6379/0"

    # --- triage -----------------------------------------------------------
    triage_provider: ProviderName = "rules"
    triage_timeout_seconds: float = Field(default=10.0, gt=0, le=10.0)
    triage_cache_ttl_seconds: int = 24 * 60 * 60

    # Groq (OpenAI-compatible). Base URL is configurable so any
    # OpenAI-compatible free tier (OpenRouter, Gemini's OpenAI endpoint) works.
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_model: str = "llama-3.1-8b-instant"
    llm_api_key: SecretStr = SecretStr("")
    llm_provider_label: str = "groq"

    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str = "llama3.2:1b"

    # SimulatedTriage failure injection (CI / tests / demo)
    simulated_failure_mode: Literal["none", "raise", "malformed", "timeout"] = "none"

    # --- redis jobs --------------------------------------------------------
    stats_cache_ttl_seconds: int = 30
    rate_limit_requests: int = 10
    rate_limit_window_seconds: int = 60
    # Only trust X-Forwarded-For / X-Real-IP when a proxy we control sits in front.
    trust_proxy_headers: bool = True

    # --- CORS (only needed when the UI is served from a different origin, e.g. `npm run dev`)
    cors_origins: str = ""

    # --- shutdown ------------------------------------------------------------
    graceful_shutdown_seconds: int = 20
    port: int = 8000

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
