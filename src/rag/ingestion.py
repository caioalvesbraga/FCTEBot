"""
Pipeline de ingestão de documentos para a base de conhecimento do FCTEBot.

Suporta: PDF, Markdown, TXT, DOCX
Estratégia de chunking: janela deslizante baseada em sentenças
"""
from __future__ import annotations

import pickle
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Generator

import numpy as np
from loguru import logger
from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import TfidfVectorizer

try:
    import faiss
except ImportError:
    raise ImportError("faiss-cpu não instalado. Execute: pip install faiss-cpu")

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None  # type: ignore

try:
    from docx import Document as DocxDocument
except ImportError:
    DocxDocument = None  # type: ignore

from src.config import Settings


# ──────────────────────────────────────────────────────────────────────────────
# Estruturas de dados
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class DocumentChunk:
    """Unidade atômica de conhecimento indexada no RAG."""
    text: str
    source: str        # nome do arquivo de origem
    source_path: str   # caminho relativo
    chunk_id: int      # índice global do chunk
    page: int = 0      # página (para PDFs)
    section: str = ""  # título da seção (para Markdown/HTML)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "source": self.source,
            "source_path": self.source_path,
            "chunk_id": self.chunk_id,
            "page": self.page,
            "section": self.section,
            "metadata": self.metadata,
        }


# ──────────────────────────────────────────────────────────────────────────────
# Leitores de documento
# ──────────────────────────────────────────────────────────────────────────────

def _read_pdf(path: Path) -> list[tuple[str, int]]:
    """Extrai texto de PDF, retornando lista de (texto, número_da_página)."""
    if PdfReader is None:
        raise ImportError("pypdf não instalado. Execute: pip install pypdf")
    reader = PdfReader(str(path))
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        text = _clean_text(text)
        if text.strip():
            pages.append((text, i))
    return pages


def _read_markdown(path: Path) -> list[tuple[str, int]]:
    """Lê Markdown e divide por seções H1/H2/H3."""
    content = path.read_text(encoding="utf-8")
    # Remove syntax Markdown mas preserva estrutura de seções
    sections = re.split(r"\n(?=#{1,3} )", content)
    return [(_clean_text(s), 0) for s in sections if s.strip()]


def _read_txt(path: Path) -> list[tuple[str, int]]:
    content = path.read_text(encoding="utf-8")
    return [(_clean_text(content), 0)]


def _read_docx(path: Path) -> list[tuple[str, int]]:
    if DocxDocument is None:
        raise ImportError("python-docx não instalado. Execute: pip install python-docx")
    doc = DocxDocument(str(path))
    text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    return [(_clean_text(text), 0)]


def _clean_text(text: str) -> str:
    """Normaliza texto: remove caracteres de controle e espaços excessivos."""
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


READERS = {
    ".pdf": _read_pdf,
    ".md": _read_markdown,
    ".markdown": _read_markdown,
    ".txt": _read_txt,
    ".docx": _read_docx,
}


# ──────────────────────────────────────────────────────────────────────────────
# Chunking semântico baseado em sentenças
# ──────────────────────────────────────────────────────────────────────────────

def _split_into_sentences(text: str) -> list[str]:
    """Divide texto em sentenças preservando contexto."""
    # Padrão para português: termina em . ! ? seguido de espaço e letra maiúscula
    pattern = r"(?<=[.!?])\s+(?=[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ\d])"
    sentences = re.split(pattern, text)
    return [s.strip() for s in sentences if s.strip()]


def _chunk_sentences(
    sentences: list[str],
    chunk_size: int,
    chunk_overlap: int,
) -> Generator[str, None, None]:
    """
    Agrupa sentenças em chunks de até chunk_size tokens aproximados,
    com sobreposição de chunk_overlap tokens entre chunks consecutivos.
    """
    if not sentences:
        return

    current_chunk: list[str] = []
    current_len = 0

    for sentence in sentences:
        # Aproximação: 1 token ≈ 4 caracteres (para português)
        sentence_len = len(sentence) // 4

        if current_len + sentence_len > chunk_size and current_chunk:
            yield " ".join(current_chunk)
            # Mantém sobreposição: guarda as últimas sentenças até overlap
            overlap_len = 0
            overlap_sentences: list[str] = []
            for s in reversed(current_chunk):
                s_len = len(s) // 4
                if overlap_len + s_len <= chunk_overlap:
                    overlap_sentences.insert(0, s)
                    overlap_len += s_len
                else:
                    break
            current_chunk = overlap_sentences
            current_len = overlap_len

        current_chunk.append(sentence)
        current_len += sentence_len

    if current_chunk:
        yield " ".join(current_chunk)


# ──────────────────────────────────────────────────────────────────────────────
# Pipeline de ingestão principal
# ──────────────────────────────────────────────────────────────────────────────

class IngestionPipeline:
    """
    Processa documentos da knowledge_base e constrói:
      - Índice FAISS (busca vetorial densa)
      - Vetorizador TF-IDF (busca esparsa)
      - Metadados dos chunks
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._embedding_model: SentenceTransformer | None = None

    def _get_embedding_model(self) -> SentenceTransformer:
        if self._embedding_model is None:
            logger.info(f"Carregando modelo de embeddings: {self.settings.embedding_model}")
            self._embedding_model = SentenceTransformer(
                self.settings.embedding_model,
                device=self.settings.embedding_device,
            )
        return self._embedding_model

    def _embed_passages(self, texts: list[str]) -> np.ndarray:
        """
        multilingual-e5 requer prefixo 'passage:' para documentos indexados
        e 'query:' para consultas (ver retrieval.py).
        """
        model = self._get_embedding_model()
        prefixed = [f"passage: {t}" for t in texts]
        embeddings = model.encode(
            prefixed,
            batch_size=32,
            show_progress_bar=True,
            normalize_embeddings=True,  # necessário para busca por cosseno com FAISS
        )
        return embeddings.astype(np.float32)

    def discover_documents(self) -> list[Path]:
        """Lista todos os documentos suportados na knowledge_base."""
        kb_path = self.settings.knowledge_base_path
        if not kb_path.exists():
            logger.warning(f"knowledge_base não encontrada em: {kb_path}")
            return []

        docs = []
        for ext in READERS:
            docs.extend(kb_path.rglob(f"*{ext}"))
        docs.sort()
        logger.info(f"Documentos encontrados: {len(docs)}")
        return docs

    def load_chunks(self, doc_paths: list[Path]) -> list[DocumentChunk]:
        """Carrega e divide todos os documentos em chunks."""
        all_chunks: list[DocumentChunk] = []
        chunk_id = 0

        for doc_path in doc_paths:
            ext = doc_path.suffix.lower()
            reader = READERS.get(ext)
            if reader is None:
                logger.warning(f"Extensão não suportada: {doc_path}")
                continue

            try:
                pages = reader(doc_path)
            except Exception as e:
                logger.error(f"Erro ao ler {doc_path.name}: {e}")
                continue

            doc_name = doc_path.name
            rel_path = str(doc_path.relative_to(self.settings.knowledge_base_path))

            for page_text, page_num in pages:
                sentences = _split_into_sentences(page_text)
                for chunk_text in _chunk_sentences(
                    sentences,
                    self.settings.chunk_size,
                    self.settings.chunk_overlap,
                ):
                    if len(chunk_text.strip()) < 30:
                        continue  # ignora chunks muito curtos
                    all_chunks.append(DocumentChunk(
                        text=chunk_text,
                        source=doc_name,
                        source_path=rel_path,
                        chunk_id=chunk_id,
                        page=page_num,
                    ))
                    chunk_id += 1

            logger.info(f"  {doc_name}: {len(pages)} página(s) processada(s)")

        logger.info(f"Total de chunks gerados: {len(all_chunks)}")
        return all_chunks

    def build_faiss_index(self, embeddings: np.ndarray) -> faiss.Index:
        """
        Constrói índice FAISS com IndexFlatIP (Inner Product).
        Como os embeddings são normalizados, IP é equivalente a cosseno.
        Para coleções grandes (>100k), usar IndexIVFFlat.
        """
        dim = embeddings.shape[1]
        n = embeddings.shape[0]

        if n > 100_000:
            # IVF para grandes coleções: busca aproximada mais rápida
            nlist = min(int(n ** 0.5), 1024)
            quantizer = faiss.IndexFlatIP(dim)
            index = faiss.IndexIVFFlat(quantizer, dim, nlist, faiss.METRIC_INNER_PRODUCT)
            index.train(embeddings)
            logger.info(f"FAISS IVFFlat: {nlist} células, {n} vetores")
        else:
            # Flat para coleções pequenas: busca exata
            index = faiss.IndexFlatIP(dim)
            logger.info(f"FAISS FlatIP: busca exata, {n} vetores de dimensão {dim}")

        index.add(embeddings)
        return index

    def build_tfidf(self, texts: list[str]) -> TfidfVectorizer:
        """Ajusta TF-IDF otimizado para português."""
        vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),       # unigramas e bigramas
            max_features=50_000,
            min_df=1,
            max_df=0.95,
            sublinear_tf=True,         # tf → 1 + log(tf), reduz dominância de termos frequentes
            strip_accents="unicode",
            analyzer="word",
        )
        vectorizer.fit(texts)
        return vectorizer

    def run(self) -> dict:
        """
        Executa o pipeline completo de ingestão.
        Retorna estatísticas do processo.
        """
        start = time.perf_counter()
        logger.info("=" * 60)
        logger.info("Iniciando pipeline de ingestão FCTEBot")
        logger.info("=" * 60)

        # 1. Descobrir documentos
        doc_paths = self.discover_documents()
        if not doc_paths:
            raise ValueError("Nenhum documento encontrado na knowledge_base/")

        # 2. Carregar e chunkar
        chunks = self.load_chunks(doc_paths)
        if not chunks:
            raise ValueError("Nenhum chunk gerado. Verifique os documentos.")

        texts = [c.text for c in chunks]
        metadata = [c.to_dict() for c in chunks]

        # 3. Embeddings (FAISS)
        logger.info("Gerando embeddings (pode levar alguns minutos)...")
        embeddings = self._embed_passages(texts)

        # 4. Índice FAISS
        logger.info("Construindo índice FAISS...")
        index = self.build_faiss_index(embeddings)

        # 5. TF-IDF
        logger.info("Ajustando TF-IDF...")
        tfidf = self.build_tfidf(texts)

        # 6. Persistir
        logger.info("Salvando índices em disco...")
        faiss.write_index(index, str(self.settings.faiss_index_path))

        with open(self.settings.faiss_metadata_path, "wb") as f:
            pickle.dump(metadata, f)

        with open(self.settings.chunks_path, "wb") as f:
            pickle.dump(texts, f)

        with open(self.settings.tfidf_path, "wb") as f:
            pickle.dump(tfidf, f)

        elapsed = time.perf_counter() - start
        stats = {
            "documents": len(doc_paths),
            "chunks": len(chunks),
            "embedding_dim": embeddings.shape[1],
            "elapsed_seconds": round(elapsed, 2),
        }
        logger.success(
            f"Ingestão concluída em {elapsed:.1f}s | "
            f"{len(doc_paths)} docs → {len(chunks)} chunks"
        )
        return stats
