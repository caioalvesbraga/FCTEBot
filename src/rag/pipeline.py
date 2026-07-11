"""
Pipeline RAG completo — orquestra cache, retrieval, re-ranking e geração.

Fluxo de uma consulta:
  query
    │
    ├─► [L1 Cache] ── hit ──► retorna resposta cacheada
    │
    ├─► [L2 Cache] ── hit ──► retorna resposta cacheada (semanticamente similar)
    │
    ├─► [Hybrid Retrieval] (TF-IDF + FAISS + RRF)
    │       │
    │       └─► top-20 chunks
    │
    ├─► [Cross-Encoder Reranker]
    │       │
    │       └─► top-5 chunks (re-ranqueados)
    │
    ├─► [Generator] (Ollama local → fallback Gemini)
    │
    ├─► [Store L1 Cache]
    │
    └─► retorna GenerationResult
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

from loguru import logger

from src.cache.redis_cache import RedisCache
from src.config import Settings
from src.monitoring.metrics import RAGMetrics
from src.rag.generator import GenerationResult, GenerationMode, RAGGenerator
from src.rag.reranker import CrossEncoderReranker
from src.rag.retrieval import HybridRetriever


@dataclass
class QueryResult:
    """Resultado completo de uma consulta ao FCTEBot."""
    query: str
    response: str
    sources: list[str]
    mode: GenerationMode
    confidence: float
    latency_total_ms: float
    latency_retrieval_ms: float
    latency_reranking_ms: float
    latency_generation_ms: float
    cache_hit: str  # "none", "l1", "l2"
    chunks_retrieved: int
    chunks_after_rerank: int
    model_used: str


class RAGPipeline:
    """
    Pipeline RAG completo com cache multinível.
    Projetado como singleton de aplicação — inicializado uma vez.
    """

    def __init__(
        self,
        settings: Settings,
        retriever: HybridRetriever,
        reranker: CrossEncoderReranker,
        generator: RAGGenerator,
        cache: Optional[RedisCache],
        metrics: Optional[RAGMetrics],
    ) -> None:
        self.settings = settings
        self.retriever = retriever
        self.reranker = reranker
        self.generator = generator
        self.cache = cache
        self.metrics = metrics

    async def query(self, user_query: str, user_id: Optional[str] = None) -> QueryResult:
        """
        Processa uma consulta do usuário pelo pipeline RAG completo.

        Args:
            user_query: Pergunta em linguagem natural
            user_id: Identificador do usuário (para métricas e rate limiting)

        Returns:
            QueryResult com resposta e metadados de performance
        """
        pipeline_start = time.perf_counter()
        cache_hit = "none"

        # ── Verificação de cache L1 (correspondência exata) ───────────────────
        if self.cache:
            cached = await self.cache.get_l1(user_query)
            if cached:
                latency = (time.perf_counter() - pipeline_start) * 1000
                logger.info(f"Cache L1 hit | latency={latency:.0f}ms | query='{user_query[:50]}'")
                if self.metrics:
                    self.metrics.record_query(
                        latency_ms=latency,
                        cache_hit="l1",
                        mode=GenerationMode.CACHED.value,
                        fallback=False,
                    )
                return QueryResult(
                    query=user_query,
                    response=cached["response"],
                    sources=cached.get("sources", []),
                    mode=GenerationMode.CACHED,
                    confidence=cached.get("confidence", 1.0),
                    latency_total_ms=latency,
                    latency_retrieval_ms=0,
                    latency_reranking_ms=0,
                    latency_generation_ms=0,
                    cache_hit="l1",
                    chunks_retrieved=0,
                    chunks_after_rerank=0,
                    model_used="cache",
                )

        # ── Verificação de cache L2 (similaridade semântica) ─────────────────
        if self.cache:
            cached = await self.cache.get_l2(user_query)
            if cached:
                latency = (time.perf_counter() - pipeline_start) * 1000
                logger.info(f"Cache L2 hit | latency={latency:.0f}ms | query='{user_query[:50]}'")
                if self.metrics:
                    self.metrics.record_query(
                        latency_ms=latency,
                        cache_hit="l2",
                        mode=GenerationMode.CACHED.value,
                        fallback=False,
                    )
                return QueryResult(
                    query=user_query,
                    response=cached["response"],
                    sources=cached.get("sources", []),
                    mode=GenerationMode.CACHED,
                    confidence=cached.get("confidence", 1.0),
                    latency_total_ms=latency,
                    latency_retrieval_ms=0,
                    latency_reranking_ms=0,
                    latency_generation_ms=0,
                    cache_hit="l2",
                    chunks_retrieved=0,
                    chunks_after_rerank=0,
                    model_used="cache",
                )

        # ── Retrieval híbrido ─────────────────────────────────────────────────
        retrieval_start = time.perf_counter()
        chunks = self.retriever.retrieve(user_query)
        retrieval_ms = (time.perf_counter() - retrieval_start) * 1000

        # ── Re-ranking ────────────────────────────────────────────────────────
        rerank_start = time.perf_counter()
        ranked_chunks = self.reranker.rerank(user_query, chunks)
        rerank_ms = (time.perf_counter() - rerank_start) * 1000

        # Formatar contexto estruturado
        context, sources = self.reranker.format_context(ranked_chunks)

        # ── Geração ───────────────────────────────────────────────────────────
        gen_result: GenerationResult = await self.generator.generate(
            query=user_query,
            context=context,
            sources=sources,
        )

        total_ms = (time.perf_counter() - pipeline_start) * 1000

        logger.info(
            f"Pipeline completo | total={total_ms:.0f}ms | "
            f"retrieval={retrieval_ms:.0f}ms | rerank={rerank_ms:.0f}ms | "
            f"gen={gen_result.latency_ms:.0f}ms | "
            f"mode={gen_result.mode.value} | chunks={len(chunks)}→{len(ranked_chunks)}"
        )

        # ── Salvar em cache L1 (se resposta confiável) ────────────────────────
        if self.cache and gen_result.confidence >= self.settings.confidence_threshold:
            cache_payload = {
                "response": gen_result.response,
                "sources": gen_result.sources,
                "confidence": gen_result.confidence,
            }
            await self.cache.set_l1(user_query, cache_payload)
            await self.cache.set_l2(user_query, cache_payload)

        # ── Métricas ──────────────────────────────────────────────────────────
        if self.metrics:
            self.metrics.record_query(
                latency_ms=total_ms,
                cache_hit="none",
                mode=gen_result.mode.value,
                fallback=(gen_result.mode == GenerationMode.FALLBACK),
            )
            self.metrics.record_retrieval(len(chunks), retrieval_ms)
            self.metrics.record_reranking(len(ranked_chunks), rerank_ms)

        return QueryResult(
            query=user_query,
            response=gen_result.response,
            sources=gen_result.sources,
            mode=gen_result.mode,
            confidence=gen_result.confidence,
            latency_total_ms=total_ms,
            latency_retrieval_ms=retrieval_ms,
            latency_reranking_ms=rerank_ms,
            latency_generation_ms=gen_result.latency_ms,
            cache_hit=cache_hit,
            chunks_retrieved=len(chunks),
            chunks_after_rerank=len(ranked_chunks),
            model_used=gen_result.model_used,
        )
