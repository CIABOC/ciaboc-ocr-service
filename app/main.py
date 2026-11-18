
import os

from fastapi import FastAPI
from app.api.routes import ocr


# Application environment
APP_ENV = os.getenv("APP_ENV", "development").lower()

# API documentation is available only during development
docs_url = "/docs" if APP_ENV == "development" else None
openapi_url = "/openapi.json" if APP_ENV == "development" else None


app = FastAPI(
    title="CIABOC OCR Service",
    description="Internal OCR service for identity document data extraction",
    version="1.0.0",
    docs_url=docs_url,
    redoc_url=None,
    openapi_url=openapi_url
)


# Register API routes
app.include_router(
    ocr.router,
    prefix="/api/v1/ocr",
    tags=["OCR"]
)


@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "service": "CIABOC OCR Service"
    }

