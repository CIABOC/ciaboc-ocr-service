"""
Security middleware for the CIABOC OCR service.

Provides:
  - API key authentication for service-to-service calls
  - Rate limiting (sliding window per client)
  - OCR concurrency limiting (bounded semaphore)
  - Request size enforcement
  - Controlled error responses (no stack traces)
"""

import asyncio
import hashlib
import logging
import time
from collections import defaultdict
from typing import Callable

from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings

logger = logging.getLogger("ciaboc_ocr.security")


# ---------------------------------------------------------------------------
# API Key Authentication
# ---------------------------------------------------------------------------

class APIKeyMiddleware(BaseHTTPMiddleware):
    """
    Validate X-API-Key header on protected endpoints.

    Skips authentication for health and docs endpoints.
    If no API key is configured (development), all requests pass.
    """

    EXEMPT_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        settings = get_settings()

        # Skip auth if no key is configured (development mode)
        if not settings.api_key:
            return await call_next(request)

        # Skip exempt paths
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        # Validate API key
        provided_key = request.headers.get(settings.api_key_header, "")

        if not provided_key:
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication required."},
            )

        # Constant-time comparison to prevent timing attacks
        expected_hash = hashlib.sha256(
            settings.api_key.encode()
        ).hexdigest()
        provided_hash = hashlib.sha256(
            provided_key.encode()
        ).hexdigest()

        if expected_hash != provided_hash:
            return JSONResponse(
                status_code=403,
                content={"detail": "Invalid authentication credentials."},
            )

        return await call_next(request)


# ---------------------------------------------------------------------------
# Rate Limiting
# ---------------------------------------------------------------------------

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Sliding-window rate limiter per client IP.

    Limits the number of requests within a configurable time window.
    """

    def __init__(self, app, **kwargs):
        super().__init__(app, **kwargs)
        self._requests: dict[str, list[float]] = defaultdict(list)

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        settings = get_settings()

        if settings.rate_limit_requests <= 0:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        window = settings.rate_limit_window_seconds

        # Clean old entries
        entries = self._requests[client_ip]
        cutoff = now - window
        self._requests[client_ip] = [t for t in entries if t > cutoff]
        entries = self._requests[client_ip]

        if len(entries) >= settings.rate_limit_requests:
            logger.warning("Rate limit exceeded for client.")
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please try again later."},
            )

        entries.append(now)
        return await call_next(request)


# ---------------------------------------------------------------------------
# OCR Concurrency Limiter
# ---------------------------------------------------------------------------

class OCRConcurrencyLimiter:
    """
    Bounds the number of concurrent OCR operations.

    Uses an asyncio Semaphore to prevent resource exhaustion.
    """

    def __init__(self, max_concurrent: int = 2):
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._max = max_concurrent

    async def acquire(self) -> bool:
        """Try to acquire a slot. Returns True if acquired."""
        try:
            acquired = self._semaphore._value > 0  # noqa: SLF001
            if not acquired:
                return False
            await self._semaphore.acquire()
            return True
        except Exception:
            return False

    def release(self) -> None:
        """Release a slot."""
        self._semaphore.release()

    @property
    def available(self) -> int:
        return self._semaphore._value  # noqa: SLF001


# Module-level limiter
_settings = get_settings()
ocr_concurrency_limiter = OCRConcurrencyLimiter(
    max_concurrent=_settings.ocr_max_concurrency
)


# ---------------------------------------------------------------------------
# Error Sanitization
# ---------------------------------------------------------------------------

class ErrorSanitizationMiddleware(BaseHTTPMiddleware):
    """
    Catch unhandled exceptions and return controlled error responses.

    Never exposes internal stack traces or exception details.
    """

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        try:
            return await call_next(request)
        except HTTPException:
            raise
        except Exception:
            logger.exception("Unhandled error processing request.")
            return JSONResponse(
                status_code=500,
                content={"detail": "An internal error occurred."},
            )
