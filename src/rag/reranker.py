"""
Re-ranking de chunks usando cross-encoder multilingual.

Por que cross-encoder ao invés de bi-encoder para re-ranking?
  - Bi-encoder (ex: FAISS): encodifica query e documento independentemente → rápido,
    porém não captura interação fina query↔documento.
  - Cross-encoder: processa query e documento conjuntamente em uma única passagem
    do transformer → atenção completa, muito mais preciso, porém mais lento.

Estratégia: bi-encoder recupera os top-20 candidatos (fase barata), 
cross-encoder re-ranqueia para top-5 (fase cara mas em poucos documentos).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
from loguru import logger
from sentence_transformers import CrossEncoder

from src.config import Settings
from src.rag.retrieval import RetrievedChunk


@dataclass
class RankedChunk:
    """Chunk após re-ranking com score de relevância cruzada."""
    chunk: RetrievedChunk
    cross_score: float  # score do cross-encoder (logit, não probabilidade)
    rank: int


class CrossEncoderReranker:
    """
    Re-ranker baseado no modelo mmarco-mMiniLMv2-L12-H384-v1.
    
    Treinado no MS MARCO multilingual — inclui dados em português,
    tornando-o adequado para re-ranking no contexto da FCTE/UnB.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._model: Optional[CrossEncoder] = None

    def _get_model(self) -> CrossEncoder:
        if self._model is None:
            logger.info(f"Carregando cross-encoder: {self.settings.reranker_model}")
            self._model = CrossEncoder(
                self.settings.reranker_model,
                max_length=512,
                device=self.settings.embedding_device,
            )
            logger.success("Cross-encoder carregado.")
        return self._model

    def rerank(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        top_k: Optional[int] = None,
    ) -> list[RankedChunk]:
        """
        Re-ranqueia chunks usando interação completa query↔documento.

        Args:
            query: Pergunta do usuário
            chunks: Candidatos da fase de recuperação híbrida
            top_k: Número de chunks a retornar após re-ranking

        Returns:
            Lista de RankedChunk ordenada por cross_score decrescente
        """
        if not chunks:
            return []

        top_k = top_k or self.settings.reranker_top_k
        model = self._get_model()

        # Pares (query, documento) para o cross-encoder
        pairs = [(query, chunk.text) for chunk in chunks]

        # Scores: logits brutos (não normalizados)
        scores: np.ndarray = model.predict(pairs, show_progress_bar=False)

        # Ordenar por score decrescente
        ranked_indices = np.argsort(scores)[::-1][:top_k]

        results = [
            RankedChunk(
                chunk=chunks[i],
                cross_score=float(scores[i]),
                rank=rank + 1,
            )
            for rank, i in enumerate(ranked_indices)
        ]

        logger.debug(
            f"Re-ranking: {len(chunks)} → {len(results)} chunks | "
            f"top_score={(results[0].cross_score if results else 0):.3f}"
        )
        return results

    def format_context(self, ranked_chunks: list[RankedChunk]) -> tuple[str, list[str]]:
        """
        Formata os chunks re-ranqueados em contexto estruturado para o LLM.

        Returns:
            (context_text, sources): texto do contexto e lista de fontes únicas
        """
        context_parts: list[str] = []
        sources: list[str] = []

        for rc in ranked_chunks:
            chunk = rc.chunk
            source_ref = f"{chunk.source}"
            if chunk.page > 0:
                source_ref += f" (p. {chunk.page})"

            context_parts.append(
                f"[Fonte: {source_ref}]\n{chunk.text}"
            )

            if source_ref not in sources:
                sources.append(source_ref)

        context = "\n\n---\n\n".join(context_parts)
        return context, sources
