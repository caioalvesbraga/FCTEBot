"""
Recuperação híbrida: TF-IDF (busca esparsa) + FAISS (busca densa)
combinados via Reciprocal Rank Fusion (RRF).

Decisão arquitetural:
  - TF-IDF captura correspondências lexicais exatas (siglas, códigos de disciplina,
    nomes próprios) — onde embeddings densos frequentemente falham.
  - FAISS + multilingual-e5 captura similaridade semântica profunda.
  - RRF é robusto a diferenças de escala entre os dois sistemas e supera
    média ponderada simples (Liu et al., 2023).
"""
from __future__ import annotations

import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
from loguru import logger
from sentence_transformers import SentenceTransformer

try:
    import faiss
except ImportError:
    raise ImportError("faiss-cpu não instalado.")

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from src.config import Settings


# ──────────────────────────────────────────────────────────────────────────────
# Estruturas de resultado
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class RetrievedChunk:
    """Chunk recuperado com metadados e scores de relevância."""
    chunk_id: int
    text: str
    source: str
    source_path: str
    page: int
    section: str
    rrf_score: float          # score final pós-fusão
    dense_rank: Optional[int] = None   # posição no ranking denso
    sparse_rank: Optional[int] = None  # posição no ranking esparso
    dense_score: float = 0.0  # score de similaridade coseno (FAISS)
    sparse_score: float = 0.0 # score TF-IDF


# ──────────────────────────────────────────────────────────────────────────────
# Reciprocal Rank Fusion
# ──────────────────────────────────────────────────────────────────────────────

def reciprocal_rank_fusion(
    rankings: list[list[int]],
    k: int = 60,
) -> dict[int, float]:
    """
    Combina múltiplos rankings usando RRF.

    score(d) = Σ  1 / (k + rank(d, Rᵢ))
                Rᵢ

    k=60 é o valor padrão da literatura (Cormack et al., 2009).
    Documentos ausentes em um ranking não recebem penalidade (score = 0).
    """
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    return scores


# ──────────────────────────────────────────────────────────────────────────────
# Motor de recuperação híbrida
# ──────────────────────────────────────────────────────────────────────────────

class HybridRetriever:
    """
    Recuperador híbrido que combina busca esparsa e densa.
    Os índices são carregados uma única vez (singleton de aplicação).
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._faiss_index: Optional[faiss.Index] = None
        self._tfidf: Optional[TfidfVectorizer] = None
        self._chunks: Optional[list[str]] = None
        self._metadata: Optional[list[dict]] = None
        self._embedding_model: Optional[SentenceTransformer] = None
        self._loaded = False

    def load(self) -> None:
        """Carrega os índices do disco. Chame uma vez na inicialização da app."""
        if self._loaded:
            return

        s = self.settings

        if not s.faiss_index_path.exists():
            raise FileNotFoundError(
                f"Índice FAISS não encontrado: {s.faiss_index_path}\n"
                "Execute 'make ingest' para construir os índices."
            )

        logger.info("Carregando índices de recuperação...")

        self._faiss_index = faiss.read_index(str(s.faiss_index_path))
        logger.info(f"  FAISS: {self._faiss_index.ntotal} vetores")

        with open(s.tfidf_path, "rb") as f:
            self._tfidf = pickle.load(f)
        logger.info(f"  TF-IDF: {len(self._tfidf.vocabulary_)} termos")

        with open(s.chunks_path, "rb") as f:
            self._chunks = pickle.load(f)

        with open(s.faiss_metadata_path, "rb") as f:
            self._metadata = pickle.load(f)

        logger.info(f"  Chunks: {len(self._chunks)}")

        logger.info(f"Carregando embedding model: {s.embedding_model}")
        self._embedding_model = SentenceTransformer(
            s.embedding_model,
            device=s.embedding_device,
        )

        self._loaded = True
        logger.success("Recuperador híbrido pronto.")

    # ── Busca densa (FAISS) ───────────────────────────────────────────────────

    def _embed_query(self, query: str) -> np.ndarray:
        """
        multilingual-e5: usa prefixo 'query:' para consultas.
        Embeddings normalizados → produto interno = cosseno.
        """
        embedding = self._embedding_model.encode(
            f"query: {query}",
            normalize_embeddings=True,
        )
        return embedding.astype(np.float32).reshape(1, -1)

    def _dense_search(
        self, query_embedding: np.ndarray, top_k: int
    ) -> tuple[list[int], list[float]]:
        scores, indices = self._faiss_index.search(query_embedding, top_k)
        # FAISS retorna -1 para slots vazios
        valid = [(int(i), float(s)) for i, s in zip(indices[0], scores[0]) if i >= 0]
        ids = [v[0] for v in valid]
        scs = [v[1] for v in valid]
        return ids, scs

    # ── Busca esparsa (TF-IDF) ────────────────────────────────────────────────

    def _sparse_search(self, query: str, top_k: int) -> tuple[list[int], list[float]]:
        query_vec = self._tfidf.transform([query])
        chunk_matrix = self._tfidf.transform(self._chunks)
        sims = cosine_similarity(query_vec, chunk_matrix)[0]
        top_indices = np.argsort(sims)[::-1][:top_k]
        top_scores = sims[top_indices]
        return top_indices.tolist(), top_scores.tolist()

    # ── Busca híbrida ─────────────────────────────────────────────────────────

    def retrieve(self, query: str, top_k: Optional[int] = None) -> list[RetrievedChunk]:
        """
        Recupera os top_k chunks mais relevantes usando busca híbrida RRF.

        Args:
            query: Pergunta do usuário em linguagem natural
            top_k: Número de chunks a retornar (default: settings.retrieval_top_k)

        Returns:
            Lista de chunks ordenados por score RRF decrescente
        """
        if not self._loaded:
            self.load()

        top_k = top_k or self.settings.retrieval_top_k
        # Busca mais candidatos para o RRF ter material suficiente
        candidate_k = min(top_k * 3, len(self._chunks))

        # Busca densa
        query_emb = self._embed_query(query)
        dense_ids, dense_scores = self._dense_search(query_emb, candidate_k)
        dense_score_map = dict(zip(dense_ids, dense_scores))

        # Busca esparsa
        sparse_ids, sparse_scores = self._sparse_search(query, candidate_k)
        sparse_score_map = dict(zip(sparse_ids, sparse_scores))

        # RRF
        rrf_scores = reciprocal_rank_fusion([dense_ids, sparse_ids])

        # Ordenar por RRF e retornar top_k
        sorted_ids = sorted(rrf_scores, key=lambda x: rrf_scores[x], reverse=True)[:top_k]

        results: list[RetrievedChunk] = []
        for rank, chunk_id in enumerate(sorted_ids):
            meta = self._metadata[chunk_id]
            dense_rank = dense_ids.index(chunk_id) if chunk_id in dense_ids else None
            sparse_rank = sparse_ids.index(chunk_id) if chunk_id in sparse_ids else None

            results.append(RetrievedChunk(
                chunk_id=chunk_id,
                text=self._chunks[chunk_id],
                source=meta.get("source", ""),
                source_path=meta.get("source_path", ""),
                page=meta.get("page", 0),
                section=meta.get("section", ""),
                rrf_score=rrf_scores[chunk_id],
                dense_rank=dense_rank,
                sparse_rank=sparse_rank,
                dense_score=dense_score_map.get(chunk_id, 0.0),
                sparse_score=sparse_score_map.get(chunk_id, 0.0),
            ))

        logger.debug(
            f"Retrieval '{query[:50]}...': "
            f"{len(results)} chunks | "
            f"top_rrf={(results[0].rrf_score if results else 0):.4f}"
        )
        return results

    def is_loaded(self) -> bool:
        return self._loaded

    def stats(self) -> dict:
        if not self._loaded:
            return {"loaded": False}
        return {
            "loaded": True,
            "total_chunks": self._faiss_index.ntotal,
            "tfidf_vocab_size": len(self._tfidf.vocabulary_),
            "embedding_model": self.settings.embedding_model,
        }
