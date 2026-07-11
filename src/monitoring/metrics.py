"""
Métricas Prometheus para o FCTEBot.

Métricas coletadas (alinhadas com os RNFs do TCC):
  - fctebot_query_latency_ms     : latência total por consulta (P50/P95/P99)
  - fctebot_query_total          : total de consultas por modo (local/fallback/cached)
  - fctebot_cache_hits_total     : hits de cache por nível (l1/l2)
  - fctebot_fallback_total       : quantidade de fallbacks para Gemini
  - fctebot_retrieval_chunks     : chunks recuperados por consulta
  - fctebot_confidence_score     : distribuição de scores de confiança
  - fctebot_ollama_errors_total  : erros do Ollama
"""
from __future__ import annotations

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    start_http_server,
    REGISTRY,
)
from loguru import logger


class RAGMetrics:
    """Singleton de métricas Prometheus para o pipeline RAG."""

    def __init__(self) -> None:
        # ── Latência ──────────────────────────────────────────────────────────
        self.query_latency = Histogram(
            "fctebot_query_latency_ms",
            "Latência total de consultas (ms)",
            buckets=[100, 500, 1000, 2000, 3000, 5000, 7000, 10000],
        )
        self.retrieval_latency = Histogram(
            "fctebot_retrieval_latency_ms",
            "Latência da fase de retrieval (ms)",
            buckets=[1, 5, 10, 50, 100, 500],
        )
        self.reranking_latency = Histogram(
            "fctebot_reranking_latency_ms",
            "Latência da fase de re-ranking (ms)",
            buckets=[10, 50, 100, 200, 500, 1000],
        )
        self.generation_latency = Histogram(
            "fctebot_generation_latency_ms",
            "Latência da fase de geração (ms)",
            buckets=[100, 500, 1000, 2000, 3000, 5000, 8000],
        )

        # ── Contadores de consulta ─────────────────────────────────────────────
        self.query_total = Counter(
            "fctebot_query_total",
            "Total de consultas processadas",
            ["mode"],  # local, fallback, cached, forbidden
        )
        self.cache_hits_total = Counter(
            "fctebot_cache_hits_total",
            "Total de hits de cache",
            ["level"],  # l1, l2
        )
        self.fallback_total = Counter(
            "fctebot_fallback_total",
            "Total de fallbacks para Gemini",
        )
        self.ollama_errors_total = Counter(
            "fctebot_ollama_errors_total",
            "Total de erros do Ollama",
        )

        # ── Distribuições ─────────────────────────────────────────────────────
        self.confidence_score = Histogram(
            "fctebot_confidence_score",
            "Distribuição de scores de confiança das respostas",
            buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
        )
        self.chunks_retrieved = Histogram(
            "fctebot_chunks_retrieved",
            "Número de chunks recuperados por consulta",
            buckets=[1, 3, 5, 10, 15, 20, 30],
        )

        # ── Gauges de estado ──────────────────────────────────────────────────
        self.active_users = Gauge(
            "fctebot_active_users",
            "Usuários ativos (últimos 5 minutos)",
        )
        self.index_chunks_total = Gauge(
            "fctebot_index_chunks_total",
            "Total de chunks no índice",
        )
        self.cache_l2_size = Gauge(
            "fctebot_cache_l2_size",
            "Número de entradas no cache L2",
        )

    def record_query(
        self,
        latency_ms: float,
        cache_hit: str,
        mode: str,
        fallback: bool,
    ) -> None:
        self.query_latency.observe(latency_ms)
        self.query_total.labels(mode=mode).inc()

        if cache_hit in ("l1", "l2"):
            self.cache_hits_total.labels(level=cache_hit).inc()

        if fallback:
            self.fallback_total.inc()

    def record_retrieval(self, n_chunks: int, latency_ms: float) -> None:
        self.retrieval_latency.observe(latency_ms)
        self.chunks_retrieved.observe(n_chunks)

    def record_reranking(self, n_chunks: int, latency_ms: float) -> None:
        self.reranking_latency.observe(latency_ms)

    def record_generation(self, latency_ms: float, confidence: float) -> None:
        self.generation_latency.observe(latency_ms)
        self.confidence_score.observe(confidence)

    def record_ollama_error(self) -> None:
        self.ollama_errors_total.inc()


_metrics_instance: RAGMetrics | None = None


def get_metrics() -> RAGMetrics:
    global _metrics_instance
    if _metrics_instance is None:
        _metrics_instance = RAGMetrics()
    return _metrics_instance


def start_metrics_server(port: int = 9090) -> None:
    """Inicia o servidor HTTP de métricas Prometheus em thread separada."""
    try:
        start_http_server(port)
        logger.info(f"Métricas Prometheus disponíveis em: http://0.0.0.0:{port}/metrics")
    except Exception as e:
        logger.warning(f"Não foi possível iniciar servidor de métricas: {e}")
