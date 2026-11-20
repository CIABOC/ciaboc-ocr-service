"""
CIABOC OCR Microservice — FastAPI Application.

This service extracts text from identity document images
(NIC, passport, driving licence) for the CIABOC Reception
Management System.

Extracted information always requires human verification.
"""

import logging

from fastapi import FastAPI

from app.core.config import get_settings
from app.core.security import (
    APIKeyMiddleware,
    RateLimitMiddleware,
    ErrorSanitizationMiddleware,
)
from app.api.routes import ocr

# ---------------------------------------------------------------------------
# Logging — never log PII (NIC numbers, names, DOBs, etc.)
# ---------------------------------------------------------------------------

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("ciaboc_ocr")

# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

docs_url = "/docs" if settings.is_development else None
openapi_url = "/openapi.json" if settings.is_development else None

app = FastAPI(
    title=settings.app_title,
    description="Internal OCR service for identity document data extraction",
    version=settings.app_version,
    docs_url=docs_url,
    redoc_url=None,
    openapi_url=openapi_url,
)

# ---------------------------------------------------------------------------
# Middleware (outermost first)
# ---------------------------------------------------------------------------

app.add_middleware(ErrorSanitizationMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(APIKeyMiddleware)

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

app.include_router(
    ocr.router,
    prefix="/api/v1/ocr",
    tags=["OCR"],
)


@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "service": "CIABOC OCR Service",
    }
