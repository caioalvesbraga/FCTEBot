"""
Configuração centralizada do FCTEBot via Pydantic Settings.
Todas as variáveis de ambiente são validadas e tipadas aqui.
"""
from __future__ import annotations

from pathlib import Path
from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        case_sensitive=False,
    )

    # ── Aplicação ─────────────────────────────────────────────────────────────
    app_name: str = "FCTEBot"
    debug: bool = False
    log_level: str = "INFO"

    # ── Telegram ──────────────────────────────────────────────────────────────
    telegram_token: str = Field(default="", description="Token do bot (@BotFather)")
    telegram_webhook_url: str = Field(default="", description="URL pública para webhook; vazio = polling")

    # ── Ollama ────────────────────────────────────────────────────────────────
    ollama_base_url: str = "http://ollama:11434"
    # qwen2.5:3b é preferido sobre llama3.2:3b para português
    ollama_model: str = "qwen2.5:3b"
    ollama_timeout: int = 60

    # ── Gemini (fallback) ─────────────────────────────────────────────────────
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"

    # Estratégia de geração: local_first | gemini_only | local_only
    llm_strategy: Literal["local_first", "gemini_only", "local_only"] = "local_first"

    # ── Embeddings ────────────────────────────────────────────────────────────
    # multilingual-e5-base: instruction-tuned para retrieval, ótimo em português
    embedding_model: str = "intfloat/multilingual-e5-base"
    embedding_device: str = "cpu"

    # ── Re-ranker ─────────────────────────────────────────────────────────────
    # mmarco: cross-encoder multilingual treinado em MS MARCO
    reranker_model: str = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
    reranker_top_k: int = 5

    # ── Paths de dados ────────────────────────────────────────────────────────
    data_dir: Path = Path("data")
    knowledge_base_path: Path = Path("knowledge_base")

    @property
    def faiss_index_path(self) -> Path:
        return self.data_dir / "faiss.index"

    @property
    def faiss_metadata_path(self) -> Path:
        return self.data_dir / "metadata.pkl"

    @property
    def tfidf_path(self) -> Path:
        return self.data_dir / "tfidf.pkl"

    @property
    def chunks_path(self) -> Path:
        return self.data_dir / "chunks.pkl"

    # ── Recuperação híbrida ───────────────────────────────────────────────────
    retrieval_top_k: int = Field(default=20, ge=1, le=100)
    # Pesos para Reciprocal Rank Fusion
    retrieval_tfidf_weight: float = Field(default=0.4, ge=0.0, le=1.0)
    retrieval_dense_weight: float = Field(default=0.6, ge=0.0, le=1.0)
    # Score de confiança abaixo do qual aciona o fallback Gemini
    confidence_threshold: float = Field(default=0.65, ge=0.0, le=1.0)

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: str = "redis://redis:6379/0"
    cache_l1_ttl: int = 604_800    # 7 dias — respostas exatas (hash SHA-256)
    cache_l2_ttl: int = 2_592_000  # 30 dias — contextos recuperados (similaridade)
    cache_l2_similarity_threshold: float = 0.95

    # ── Ingestão ──────────────────────────────────────────────────────────────
    chunk_size: int = Field(default=512, ge=128, le=2048)
    chunk_overlap: int = Field(default=64, ge=0, le=256)

    # ── Geração ───────────────────────────────────────────────────────────────
    temperature: float = Field(default=0.2, ge=0.0, le=1.0)
    max_tokens: int = Field(default=1024, ge=128, le=4096)

    # ── Rate Limiting ─────────────────────────────────────────────────────────
    rate_limit_per_user: int = 30  # requisições por minuto

    # ── Monitoramento ─────────────────────────────────────────────────────────
    metrics_port: int = 9090

    @model_validator(mode="after")
    def _ensure_data_dir(self) -> "Settings":
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return self

    @property
    def ollama_v1_url(self) -> str:
        """Endpoint compatível com OpenAI SDK."""
        return f"{self.ollama_base_url}/v1"

    @property
    def has_gemini(self) -> bool:
        return bool(self.gemini_api_key)

    @property
    def gemini_key_valid(self) -> bool:
        """Aceita chaves AI Studio: AIza (legado) ou AQ. (auth key, padrão desde 2026)."""
        key = self.gemini_api_key.strip()
        return key.startswith("AIza") or key.startswith("AQ.")

    @property
    def gemini_key_type(self) -> str:
        key = self.gemini_api_key.strip()
        if key.startswith("AQ."):
            return "auth"
        if key.startswith("AIza"):
            return "standard"
        return "unknown"

    @property
    def gemini_configured(self) -> bool:
        return self.has_gemini and self.gemini_key_valid

    @property
    def has_telegram(self) -> bool:
        return bool(self.telegram_token)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Retorna instância singleton das configurações."""
    return Settings()
