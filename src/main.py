"""
Entry point da aplicação FCTEBot.

Inicialização na ordem:
  1. Configuração (Pydantic Settings)
  2. Logging (Loguru)
  3. Métricas (Prometheus)
  4. Cache Redis
  5. Retriever híbrido (carrega índices FAISS + TF-IDF)
  6. Re-ranker (carrega cross-encoder)
  7. Gerador (configura Ollama + Gemini)
  8. Pipeline RAG (orquestra todos os componentes)
  9. Bot Telegram (modo webhook ou polling)
  10. FastAPI app
"""
from __future__ import annotations

import asyncio
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from src.api.middleware import RateLimitMiddleware, RequestLoggingMiddleware
from src.api.routes import router
from src.bot.telegram_handler import build_bot_app, setup_bot_commands
from src.cache.redis_cache import RedisCache
from src.config import Settings, get_settings
from src.monitoring.metrics import RAGMetrics, get_metrics, start_metrics_server
from src.rag.generator import RAGGenerator
from src.rag.pipeline import RAGPipeline
from src.rag.reranker import CrossEncoderReranker
from src.rag.retrieval import HybridRetriever


# ──────────────────────────────────────────────────────────────────────────────
# Configurar Loguru
# ──────────────────────────────────────────────────────────────────────────────

def configure_logging(settings: Settings) -> None:
    logger.remove()
    logger.add(
        sys.stderr,
        level=settings.log_level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> — "
            "<level>{message}</level>"
        ),
        colorize=True,
    )
    logger.add(
        "logs/fctebot.log",
        level="DEBUG",
        rotation="10 MB",
        retention="30 days",
        compression="gz",
        format="{time} | {level} | {name}:{function}:{line} — {message}",
    )


# ──────────────────────────────────────────────────────────────────────────────
# Lifespan (inicialização e desligamento)
# ──────────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia o ciclo de vida completo da aplicação."""
    settings = get_settings()
    configure_logging(settings)

    logger.info("=" * 60)
    logger.info(f"Iniciando {settings.app_name} v2.0.0")
    logger.info(f"LLM strategy: {settings.llm_strategy} | Ollama: {settings.ollama_model}")
    if settings.has_gemini:
        if settings.gemini_key_valid:
            logger.info(
                f"Gemini configurado: {settings.gemini_model} "
                f"(chave {settings.gemini_key_type})"
            )
        else:
            logger.error(
                "GEMINI_API_KEY com formato desconhecido — "
                "use chave do AI Studio (AIza... ou AQ....)"
            )
    else:
        logger.warning("GEMINI_API_KEY não configurada — fallback desativado")
    logger.info("=" * 60)

    # ── Métricas ──────────────────────────────────────────────────────────────
    metrics = get_metrics()
    start_metrics_server(port=settings.metrics_port)

    # ── Cache Redis ───────────────────────────────────────────────────────────
    cache: Optional[RedisCache] = None
    try:
        cache = RedisCache(settings)
        await cache.connect()
        app.state.cache = cache
    except Exception as e:
        logger.warning(f"Redis indisponível: {e} — operando sem cache")
        cache = None

    # ── Componentes RAG ───────────────────────────────────────────────────────
    retriever = HybridRetriever(settings)
    reranker = CrossEncoderReranker(settings)
    generator = RAGGenerator(settings)

    # Tenta carregar índices (pode não existir ainda — usuário deve rodar ingest)
    try:
        retriever.load()
        app.state.pipeline = RAGPipeline(
            settings=settings,
            retriever=retriever,
            reranker=reranker,
            generator=generator,
            cache=cache,
            metrics=metrics,
        )
        logger.success("Pipeline RAG inicializado.")
    except FileNotFoundError as e:
        logger.warning(f"{e}")
        logger.warning(
            "Pipeline RAG NÃO inicializado. Execute 'make ingest' para construir os índices."
        )
        app.state.pipeline = None

    # ── Bot Telegram ──────────────────────────────────────────────────────────
    bot_app = None
    if settings.has_telegram and app.state.pipeline:
        try:
            bot_app = build_bot_app(settings, app.state.pipeline)
            await bot_app.initialize()
            await setup_bot_commands(bot_app)

            if settings.telegram_webhook_url:
                await bot_app.bot.set_webhook(
                    url=f"{settings.telegram_webhook_url}/webhook",
                    allowed_updates=["message"],
                )
                logger.info(f"Webhook Telegram configurado: {settings.telegram_webhook_url}/webhook")
            else:
                # Modo polling (desenvolvimento)
                await bot_app.start()
                asyncio.create_task(bot_app.updater.start_polling())
                logger.info("Bot Telegram em modo polling (desenvolvimento)")

            app.state.bot_app = bot_app
        except Exception as e:
            logger.error(f"Erro ao inicializar bot Telegram: {e}")
    elif not settings.has_telegram:
        logger.warning("TELEGRAM_TOKEN não configurado — bot desativado")

    logger.success(f"{settings.app_name} pronto! API: http://0.0.0.0:8000")

    yield  # Aplicação rodando

    # ── Desligamento ──────────────────────────────────────────────────────────
    logger.info("Encerrando FCTEBot...")

    if bot_app:
        if settings.telegram_webhook_url:
            await bot_app.bot.delete_webhook()
        else:
            await bot_app.updater.stop()
        await bot_app.stop()
        await bot_app.shutdown()

    if cache:
        await cache.disconnect()

    logger.info("FCTEBot encerrado.")


# ──────────────────────────────────────────────────────────────────────────────
# Aplicação FastAPI
# ──────────────────────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description=(
            "Assistente Virtual Educacional da FCTE/UnB — "
            "Arquitetura RAG Local-First com modelos open-source"
        ),
        version="2.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Middleware (ordem importa: CORS → logging → rate limit)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(RateLimitMiddleware, requests_per_minute=settings.rate_limit_per_user)

    # Arquivos estáticos (interface web)
    static_dir = Path(__file__).parent / "api" / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # Rota da interface de chat
    @app.get("/chat", include_in_schema=False)
    async def chat_ui():
        chat_html = static_dir / "chat" / "index.html"
        return FileResponse(str(chat_html))

    # Rotas da API
    app.include_router(router)

    return app


app = create_app()


# ──────────────────────────────────────────────────────────────────────────────
# Execução direta
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=get_settings().debug,
        log_level=get_settings().log_level.lower(),
    )
