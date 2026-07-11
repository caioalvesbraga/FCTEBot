"""
Script CLI de ingestão da base de conhecimento.

Uso:
  python scripts/ingest.py [--kb-path knowledge_base/] [--force]

Pode ser executado:
  - Manualmente: python scripts/ingest.py
  - Via Make: make ingest
  - Via Docker: docker exec fctebot-app python scripts/ingest.py
  - Via GitHub Actions: workflow automatizado em .github/workflows/ingest.yml
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Garantir que o módulo src seja encontrado independente do diretório de execução
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from src.config import get_settings
from src.rag.ingestion import IngestionPipeline


def main() -> None:
    parser = argparse.ArgumentParser(
        description="FCTEBot — Pipeline de Ingestão da Base de Conhecimento",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python scripts/ingest.py
  python scripts/ingest.py --kb-path /caminho/para/docs/
  python scripts/ingest.py --force  # recria índice mesmo que já exista
        """,
    )
    parser.add_argument(
        "--kb-path",
        type=Path,
        default=None,
        help="Caminho para a base de conhecimento (default: KNOWLEDGE_BASE_PATH do .env)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Força re-ingestão mesmo que os índices já existam",
    )
    args = parser.parse_args()

    settings = get_settings()

    # Sobrescrever kb_path se fornecido
    if args.kb_path:
        settings.knowledge_base_path = args.kb_path

    # Verificar se índices já existem
    if not args.force and settings.faiss_index_path.exists():
        logger.warning(
            f"Índice FAISS já existe em: {settings.faiss_index_path}\n"
            "Use --force para re-indexar."
        )
        response = input("Deseja continuar e sobrescrever? [s/N]: ").strip().lower()
        if response != "s":
            logger.info("Ingestão cancelada.")
            return

    # Executar pipeline
    pipeline = IngestionPipeline(settings)
    try:
        stats = pipeline.run()
        print("\n✓ Ingestão concluída com sucesso!")
        print(f"  Documentos processados: {stats['documents']}")
        print(f"  Chunks gerados:         {stats['chunks']}")
        print(f"  Dimensão dos embeddings:{stats['embedding_dim']}")
        print(f"  Tempo total:            {stats['elapsed_seconds']}s")
        print(f"\n  Índice FAISS: {settings.faiss_index_path}")
        print(f"  TF-IDF:       {settings.tfidf_path}")
        print(f"  Metadados:    {settings.faiss_metadata_path}")
    except Exception as e:
        logger.error(f"Erro na ingestão: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
