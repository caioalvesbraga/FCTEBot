"""
Cache multinível com Redis para o FCTEBot.

L1 — Exact Match Cache:
  - Chave: SHA-256(query normalizada)
  - TTL: 7 dias
  - Hit ratio esperado: 15-20% (consultas idênticas por diferentes alunos)
  - Latência de resposta: < 5ms

L2 — Semantic Similarity Cache:
  - Armazena embeddings das queries cacheadas
  - Busca por similaridade coseno (threshold: 0.95)
  - TTL: 30 dias
  - Hit ratio esperado: 40-50% (consultas semanticamente similares)
  - Latência: ~20ms (busca no vetor de embeddings em memória)

Decisão de implementação:
  Optou-se por armazenar os embeddings do L2 em memória Python (dict)
  em vez de Redis Vector Search (módulo adicional pago/enterprise).
  Isso mantém compatibilidade com Redis Community Edition, 
  adequado para uso em instituição pública.
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import Optional

import numpy as np
from loguru import logger

try:
    import redis.asyncio as aioredis
    from redis.asyncio import Redis
except ImportError:
    raise ImportError("redis[asyncio] não instalado. Execute: pip install redis[asyncio]")

from src.config import Settings

# Prefixos de chave Redis para evitar colisões de namespace
_PREFIX_L1 = "fctebot:l1:"
_PREFIX_L2_DATA = "fctebot:l2:data:"
_PREFIX_L2_INDEX = "fctebot:l2:index"


def _normalize_query(query: str) -> str:
    """Normaliza query para chave de cache: minúsculas, sem espaços extras."""
    return " ".join(query.lower().split())


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class RedisCache:
    """Cache assíncrono multinível com Redis."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._redis: Optional[Redis] = None
        # Índice L2 em memória: {cache_key: embedding_array}
        # Carregado do Redis na inicialização para buscas rápidas
        self._l2_index: dict[str, np.ndarray] = {}
        self._l2_index_loaded = False

    async def connect(self) -> None:
        """Conecta ao Redis e carrega o índice L2."""
        self._redis = aioredis.from_url(
            self.settings.redis_url,
            encoding="utf-8",
            decode_responses=False,  # bytes para serialização de embeddings
        )
        await self._redis.ping()
        await self._load_l2_index()
        logger.success(
            f"Redis conectado | L2 index: {len(self._l2_index)} entradas carregadas"
        )

    async def disconnect(self) -> None:
        if self._redis:
            await self._redis.aclose()

    async def _load_l2_index(self) -> None:
        """Carrega embeddings do L2 index do Redis para memória."""
        if not self._redis:
            return
        try:
            index_keys = await self._redis.smembers(_PREFIX_L2_INDEX)
            for key in index_keys:
                key_str = key.decode() if isinstance(key, bytes) else key
                emb_bytes = await self._redis.hget(f"{_PREFIX_L2_DATA}{key_str}", "embedding")
                if emb_bytes:
                    self._l2_index[key_str] = np.frombuffer(emb_bytes, dtype=np.float32)
        except Exception as e:
            logger.warning(f"Falha ao carregar índice L2: {e}")
        self._l2_index_loaded = True

    # ── Cache L1: correspondência exata ───────────────────────────────────────

    async def get_l1(self, query: str) -> Optional[dict]:
        """
        Busca resposta cacheada por correspondência exata (SHA-256).
        Retorna dict com {response, sources, confidence} ou None.
        """
        if not self._redis:
            return None
        key = f"{_PREFIX_L1}{_sha256(_normalize_query(query))}"
        try:
            raw = await self._redis.get(key)
            if raw:
                return json.loads(raw)
        except Exception as e:
            logger.warning(f"Cache L1 get error: {e}")
        return None

    async def set_l1(self, query: str, payload: dict) -> None:
        """Armazena resposta no L1 cache com TTL configurado."""
        if not self._redis:
            return
        key = f"{_PREFIX_L1}{_sha256(_normalize_query(query))}"
        try:
            await self._redis.setex(
                key,
                self.settings.cache_l1_ttl,
                json.dumps(payload, ensure_ascii=False),
            )
        except Exception as e:
            logger.warning(f"Cache L1 set error: {e}")

    # ── Cache L2: similaridade semântica ──────────────────────────────────────

    async def get_l2(self, query: str, query_embedding: Optional[np.ndarray] = None) -> Optional[dict]:
        """
        Busca resposta cacheada por similaridade semântica.

        Se query_embedding não for fornecido, apenas verifica se há entradas
        no índice (sem calcular similaridade — embedding calculado externamente).

        Args:
            query: Texto da consulta
            query_embedding: Embedding normalizado da query (dim=768 para e5-base)

        Returns:
            dict cacheado se similaridade > threshold, ou None
        """
        if not self._redis or not self._l2_index or query_embedding is None:
            return None

        # Busca por similaridade coseno (embeddings já normalizados → produto interno)
        best_key: Optional[str] = None
        best_score = 0.0

        for cache_key, cached_emb in self._l2_index.items():
            score = float(np.dot(query_embedding, cached_emb))
            if score > best_score:
                best_score = score
                best_key = cache_key

        if best_key and best_score >= self.settings.cache_l2_similarity_threshold:
            logger.debug(f"Cache L2 similarity: {best_score:.4f} > {self.settings.cache_l2_similarity_threshold}")
            try:
                raw = await self._redis.hget(f"{_PREFIX_L2_DATA}{best_key}", "payload")
                if raw:
                    return json.loads(raw)
            except Exception as e:
                logger.warning(f"Cache L2 get error: {e}")

        return None

    async def set_l2(
        self,
        query: str,
        payload: dict,
        query_embedding: Optional[np.ndarray] = None,
    ) -> None:
        """
        Armazena resposta no L2 cache com embedding para busca semântica futura.
        Se embedding não fornecido, apenas persiste o payload (sem indexação semântica).
        """
        if not self._redis:
            return

        cache_key = _sha256(_normalize_query(query))
        data_key = f"{_PREFIX_L2_DATA}{cache_key}"

        try:
            pipe = self._redis.pipeline()

            # Payload da resposta
            await pipe.hset(data_key, "payload", json.dumps(payload, ensure_ascii=False))
            await pipe.expire(data_key, self.settings.cache_l2_ttl)

            # Embedding (se disponível)
            if query_embedding is not None:
                emb_bytes = query_embedding.astype(np.float32).tobytes()
                await pipe.hset(data_key, "embedding", emb_bytes)
                # Atualizar índice em memória
                self._l2_index[cache_key] = query_embedding.astype(np.float32)

            # Registrar no set de chaves do índice
            await pipe.sadd(_PREFIX_L2_INDEX, cache_key)

            await pipe.execute()

        except Exception as e:
            logger.warning(f"Cache L2 set error: {e}")

    async def invalidate_all(self) -> int:
        """Remove todo o cache (usar após atualização da knowledge_base)."""
        if not self._redis:
            return 0
        count = 0
        async for key in self._redis.scan_iter(f"fctebot:*"):
            await self._redis.delete(key)
            count += 1
        self._l2_index.clear()
        logger.info(f"Cache invalidado: {count} chaves removidas")
        return count

    async def stats(self) -> dict:
        """Retorna estatísticas do cache."""
        if not self._redis:
            return {"connected": False}
        try:
            info = await self._redis.info("memory")
            l1_count = 0
            async for _ in self._redis.scan_iter(f"{_PREFIX_L1}*"):
                l1_count += 1
            return {
                "connected": True,
                "l1_entries": l1_count,
                "l2_entries": len(self._l2_index),
                "memory_used_mb": round(info.get("used_memory", 0) / 1024 / 1024, 2),
            }
        except Exception as e:
            logger.warning(f"Cache stats error: {e}")
            return {"connected": False, "error": str(e)}
