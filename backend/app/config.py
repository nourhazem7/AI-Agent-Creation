"""AgentForge backend configuration — its own settings, independent of text2sql."""

from __future__ import annotations

import json
import logging
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    secret_key: str = "dev-secret-key-change-me"
    access_token_expire_minutes: int = 1440

    fernet_key: str = ""

    # LLM configuration — provider-agnostic, mirrors TextSQL's own constructor params
    # exactly (model, base_url, verify_ssl, extra_body, llm_api_key). Defaults match the
    # text2sql framework's own documented reference deployment (see TextSQL's docstring
    # in text2sql/core.py and the default ConnectRequest in text2sql/api.py) — the
    # company's existing OpenAI-compatible endpoint, not a hardcoded provider choice.
    # Change these to point at a different provider/endpoint without touching any code.
    llm_model: str = "openai:Qwen/Qwen3.6-35B-A3B"
    llm_base_url: str = "https://ibm-models.elsewedy-ec.com/v1"
    llm_verify_ssl: bool = False
    # JSON-encoded dict (env vars are strings) — merged into every LLM request body.
    llm_extra_body: str = '{"chat_template_kwargs": {"enable_thinking": false}}'
    # Optional. Left empty when the configured endpoint doesn't require one (the
    # framework itself falls back to a "not-required" placeholder in that case) —
    # never invent a key here.
    llm_api_key: str = ""

    database_url: str = "sqlite:///./data/agentforge.db"

    cors_origins: str = "http://localhost:5173"

    storage_dir: str = "storage"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def llm_extra_body_dict(self) -> dict | None:
        if not self.llm_extra_body:
            return None
        try:
            return json.loads(self.llm_extra_body)
        except json.JSONDecodeError:
            logger.warning("LLM_EXTRA_BODY is not valid JSON — ignoring it: %r", self.llm_extra_body)
            return None


@lru_cache
def get_settings() -> Settings:
    return Settings()
