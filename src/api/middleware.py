"""
Middleware FastAPI: rate limiting por usuário + logging estruturado de requisições.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting por IP/user_id: sliding window de 1 minuto.
    Alinhado ao RNF004 (suporte a 50 usuários simultâneos).
    """

    def __init__(self, app, requests_per_minute: int = 30) -> None:
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        # {client_id: deque de timestamps das requisições}
        self._windows: dict[str, deque] = defaultdict(deque)

    def _get_client_id(self, request: Request) -> str:
        """Extrai identificador do cliente (IP ou header X-User-Id)."""
        user_id = request.headers.get("X-User-Id")
        if user_id:
            return f"user:{user_id}"
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return f"ip:{forwarded.split(',')[0].strip()}"
        return f"ip:{request.client.host if request.client else 'unknown'}"

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Não aplica rate limit a health checks e métricas
        if request.url.path in ("/health", "/metrics", "/"):
            return await call_next(request)

        client_id = self._get_client_id(request)
        now = time.monotonic()
        window = self._windows[client_id]

        # Remove timestamps fora da janela de 60s
        while window and now - window[0] > 60:
            window.popleft()

        if len(window) >= self.requests_per_minute:
            logger.warning(f"Rate limit atingido: {client_id}")
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limit_exceeded",
                    "message": "Muitas requisições. Aguarde 1 minuto.",
                    "retry_after": 60,
                },
            )

        window.append(now)
        return await call_next(request)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logging estruturado de todas as requisições com latência."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        latency_ms = (time.perf_counter() - start) * 1000

        logger.info(
            f"{request.method} {request.url.path} → {response.status_code} "
            f"({latency_ms:.0f}ms)"
        )
        response.headers["X-Response-Time-Ms"] = str(round(latency_ms))
        return response
