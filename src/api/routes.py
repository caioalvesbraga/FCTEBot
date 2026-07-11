"""
Rotas FastAPI do FCTEBot.

Endpoints:
  GET  /            → informações básicas da API
  GET  /health      → health check de todos os componentes
  POST /query       → consulta ao pipeline RAG
  POST /webhook     → webhook do Telegram
  POST /ingest      → disparar re-ingestão da knowledge_base
  DELETE /cache     → invalidar todo o cache
  GET  /cache/stats → estatísticas do cache
  GET  /retriever/stats → estatísticas do índice
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import BaseModel, Field

from src.config import Settings, get_settings
from src.rag.pipeline import RAGPipeline


# ──────────────────────────────────────────────────────────────────────────────
# Schemas Pydantic de request/response
# ──────────────────────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=1000, description="Pergunta do usuário")
    user_id: Optional[str] = Field(None, description="ID do usuário para métricas")

class QueryResponse(BaseModel):
    response: str
    sources: list[str]
    mode: str        # local, fallback, cached, forbidden
    confidence: float
    latency_ms: float
    cache_hit: str   # none, l1, l2
    model_used: str

class HealthStatus(BaseModel):
    status: str      # ok, degraded, error
    retriever: bool
    cache: bool
    ollama: bool
    gemini: bool
    gemini_key_valid: bool
    gemini_key_type: str
    llm_strategy: str
    index_chunks: int


# ──────────────────────────────────────────────────────────────────────────────
# Router
# ──────────────────────────────────────────────────────────────────────────────

router = APIRouter()


def get_pipeline(request: Request) -> RAGPipeline:
    """Injeta o pipeline RAG do estado da aplicação."""
    pipeline: Optional[RAGPipeline] = request.app.state.pipeline
    if pipeline is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Pipeline RAG não inicializado. Execute 'make ingest' primeiro.",
        )
    return pipeline


@router.get("/", summary="Informações da API")
async def root(settings: Settings = Depends(get_settings)):
    return {
        "name": settings.app_name,
        "version": "2.0.0",
        "description": "FCTEBot — Assistente Virtual Educacional com RAG Local-First",
        "docs": "/docs",
    }


@router.get("/health", response_model=HealthStatus, summary="Health Check")
async def health_check(request: Request):
    """
    Verifica saúde de todos os componentes.
    Responde 200 se status='ok', 503 se status='error'.
    """
    retriever_ok = False
    cache_ok = False
    ollama_ok = False
    gemini_ok = False
    index_chunks = 0

    # Verificar retriever
    pipeline: Optional[RAGPipeline] = getattr(request.app.state, "pipeline", None)
    try:
        if pipeline and pipeline.retriever.is_loaded():
            retriever_ok = True
            stats = pipeline.retriever.stats()
            index_chunks = stats.get("total_chunks", 0)
    except Exception:
        pass

    # Verificar cache — checa app.state.cache diretamente (existe mesmo sem pipeline)
    try:
        cache = getattr(request.app.state, "cache", None)
        if cache is None and pipeline:
            cache = pipeline.cache
        if cache:
            cache_stats = await cache.stats()
            cache_ok = cache_stats.get("connected", False)
    except Exception:
        pass

    # Verificar Ollama (ping rápido)
    try:
        import httpx
        settings = get_settings()
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/tags")
            ollama_ok = resp.status_code == 200
    except Exception:
        pass

    settings = get_settings()
    gemini_ok = settings.gemini_configured

    overall = "ok" if retriever_ok else ("degraded" if cache_ok else "error")

    response_data = HealthStatus(
        status=overall,
        retriever=retriever_ok,
        cache=cache_ok,
        ollama=ollama_ok,
        gemini=gemini_ok,
        gemini_key_valid=settings.gemini_key_valid if settings.has_gemini else False,
        gemini_key_type=settings.gemini_key_type if settings.has_gemini else "none",
        llm_strategy=settings.llm_strategy,
        index_chunks=index_chunks,
    )

    status_code = 200 if overall != "error" else 503
    return JSONResponse(content=response_data.model_dump(), status_code=status_code)


@router.post("/query", response_model=QueryResponse, summary="Consulta ao FCTEBot")
async def query_endpoint(
    body: QueryRequest,
    pipeline: RAGPipeline = Depends(get_pipeline),
):
    """
    Processa uma pergunta pelo pipeline RAG completo.

    Retorna resposta com fontes, modo de geração e métricas de latência.
    """
    try:
        result = await pipeline.query(
            user_query=body.query,
            user_id=body.user_id,
        )
        return QueryResponse(
            response=result.response,
            sources=result.sources,
            mode=result.mode.value,
            confidence=round(result.confidence, 3),
            latency_ms=round(result.latency_total_ms, 1),
            cache_hit=result.cache_hit,
            model_used=result.model_used,
        )
    except Exception as e:
        logger.exception("Erro no pipeline RAG")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno ao processar consulta. Tente novamente.",
        )


@router.post("/webhook", summary="Webhook Telegram")
async def telegram_webhook(request: Request):
    """
    Recebe updates do Telegram via webhook.
    Delega ao handler assíncrono do bot.
    """
    bot_app = getattr(request.app.state, "bot_app", None)
    if bot_app is None:
        raise HTTPException(status_code=503, detail="Bot Telegram não inicializado")

    try:
        from telegram import Update
        data = await request.json()
        update = Update.de_json(data, bot_app.bot)
        await bot_app.process_update(update)
        return {"ok": True}
    except Exception as e:
        logger.error(f"Erro no webhook Telegram: {e}")
        raise HTTPException(status_code=500, detail="Erro ao processar update")


@router.post("/ingest", summary="Disparar re-ingestão")
async def trigger_ingest(request: Request):
    """
    Dispara o pipeline de ingestão em background.
    Invalida o cache após re-ingestão.
    """
    import asyncio
    from src.rag.ingestion import IngestionPipeline
    settings = get_settings()

    async def _run_ingest():
        pipeline = IngestionPipeline(settings)
        stats = pipeline.run()

        # Recarregar retriever
        rag_pipeline: Optional[RAGPipeline] = getattr(request.app.state, "pipeline", None)
        if rag_pipeline:
            rag_pipeline.retriever.load()
            if rag_pipeline.cache:
                await rag_pipeline.cache.invalidate_all()
        return stats

    try:
        stats = await asyncio.get_event_loop().run_in_executor(None, lambda: None)
        asyncio.create_task(_run_ingest())
        return {"status": "ingestão iniciada em background", "message": "Use /health para verificar quando concluir"}
    except Exception as e:
        logger.error(f"Erro ao iniciar ingestão: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/cache", summary="Invalidar cache")
async def clear_cache(pipeline: RAGPipeline = Depends(get_pipeline)):
    """Remove todas as entradas do cache Redis."""
    if not pipeline.cache:
        raise HTTPException(status_code=503, detail="Cache não disponível")
    count = await pipeline.cache.invalidate_all()
    return {"deleted_keys": count, "message": "Cache invalidado com sucesso"}


@router.get("/cache/stats", summary="Estatísticas do cache")
async def cache_stats(pipeline: RAGPipeline = Depends(get_pipeline)):
    if not pipeline.cache:
        return {"connected": False}
    return await pipeline.cache.stats()


@router.get("/retriever/stats", summary="Estatísticas do retriever")
async def retriever_stats(pipeline: RAGPipeline = Depends(get_pipeline)):
    return pipeline.retriever.stats()
