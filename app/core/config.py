"""
app/core/config.py
──────────────────
Single source of truth for all environment-driven configuration.
Import get_settings() everywhere — never read os.environ directly.
"""
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
 
 
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="config/.env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
 
    # ── App ────────────────────────────────────────────────────────────
    app_name: str = "MindVault"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "info"
    secret_key: str = "change-me"
 
    # ── PageIndex ──────────────────────────────────────────────────────
    pageindex_api_key: str = Field(default="", description="PageIndex API key from dash.pageindex.ai")
 
    # ── LLM ────────────────────────────────────────────────────────────
    llm_provider: str = "gemini"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    gemini_api_key: str = "AIzaSyCqvi53zNMS5w7tr5GS_R9HTwgQgGmb9Ls"
    llm_model: str = "gemini-2.5-flash"
    llm_max_tokens: int = 2048
    llm_temperature: float = 0.2
 
    # ── Database ───────────────────────────────────────────────────────
    database_url: str = "sqlite+aiosqlite:///./data/mindvault.db"
 
    # ── BM25 ───────────────────────────────────────────────────────────
    bm25_k1: float = 1.5
    bm25_b: float = 0.75
    bm25_top_k: int = 10
 
    # ── PageIndex retrieval ────────────────────────────────────────────
    pi_top_k: int = 5
    pi_poll_interval_sec: float = 2.0
    pi_poll_timeout_sec: float = 120.0
 
    # ── Hybrid fusion ──────────────────────────────────────────────────
    hybrid_alpha: float = 0.5   # 0 = pure BM25 → 1 = pure PageIndex
    final_top_k: int = 5
 
    # ── Ingestion ──────────────────────────────────────────────────────
    max_upload_size_mb: int = 50
    chunk_size_tokens: int = 400
    chunk_overlap_tokens: int = 50
 
    # ── Notion ─────────────────────────────────────────────────────────
    notion_token: str = ""
    notion_workspace_id: str = ""
 
    # ── Computed helpers ───────────────────────────────────────────────
    @property
    def is_production(self) -> bool:
        return self.app_env == "production"
 
    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024
 
    @property
    def active_llm_key(self) -> str:
        if self.llm_provider == "anthropic":
            return self.anthropic_api_key
        if self.llm_provider == "gemini":
            return self.gemini_api_key
        return self.openai_api_key
 
 
@lru_cache
def get_settings() -> Settings:
    """Cached singleton — safe to call at module level."""
    return Settings()
 






'''




"""
app/core/config.py
──────────────────
Single source of truth for all environment-driven configuration.
Import get_settings() everywhere — never read os.environ directly.
"""
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="config/.env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ────────────────────────────────────────────────────────────
    app_name: str = "MindVault"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "info"
    secret_key: str = "change-me"

    # ── PageIndex ──────────────────────────────────────────────────────
    pageindex_api_key: str = Field(default="", description="")

    # ── LLM ────────────────────────────────────────────────────────────
    llm_provider: str = "anthropic"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    llm_model: str = "claude-sonnet-4-6"
    llm_max_tokens: int = 2048
    llm_temperature: float = 0.2

    # ── Database ───────────────────────────────────────────────────────
    database_url: str = "sqlite+aiosqlite:///./data/mindvault.db"

    # ── BM25 ───────────────────────────────────────────────────────────
    bm25_k1: float = 1.5
    bm25_b: float = 0.75
    bm25_top_k: int = 10

    # ── PageIndex retrieval ────────────────────────────────────────────
    pi_top_k: int = 5
    pi_poll_interval_sec: float = 2.0
    pi_poll_timeout_sec: float = 120.0

    # ── Hybrid fusion ──────────────────────────────────────────────────
    hybrid_alpha: float = 0.5   # 0 = pure BM25 → 1 = pure PageIndex
    final_top_k: int = 5

    # ── Ingestion ──────────────────────────────────────────────────────
    max_upload_size_mb: int = 50
    chunk_size_tokens: int = 400
    chunk_overlap_tokens: int = 50

    # ── Notion ─────────────────────────────────────────────────────────
    notion_token: str = ""
    notion_workspace_id: str = ""

    # ── Computed helpers ───────────────────────────────────────────────
    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def active_llm_key(self) -> str:
        return (
            self.anthropic_api_key
            if self.llm_provider == "anthropic"
            else self.openai_api_key
        )


@lru_cache
def get_settings() -> Settings:
    """Cached singleton — safe to call at module level."""
    return Settings()



'''