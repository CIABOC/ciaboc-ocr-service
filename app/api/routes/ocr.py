"""
OCR API routes.

Endpoints:
  GET  /status   – OCR service availability check
  POST /extract  – Upload an image and extract text + structured fields
"""

import logging
import time

from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from starlette.concurrency import run_in_threadpool

from app.utils.image_processor import (
    validate_image,
    ImageValidationError,
    MAX_IMAGE_SIZE,
)
from app.services.ocr_service import ocr_service
from app.services.document_extraction_service import (
    document_extraction_service,
)
from app.core.security import ocr_concurrency_limiter
from app.core.config import get_settings
from app.schemas.ocr_schema import OCRResponse

logger = logging.getLogger("ciaboc_ocr.api")

router = APIRouter()

CHUNK_SIZE = 1024 * 1024


@router.get("/status")
async def ocr_status():
    return {
        "status": "available",
        "message": "OCR service is ready",
    }


@router.post("/extract", response_model=OCRResponse)
async def extract_document(
    file: UploadFile = File(...),
    document_type: str | None = Query(
        None,
        description="Optional document type hint: NIC, PASSPORT, or DRIVING_LICENCE",
    ),
):
    """
    Upload an identity document image and extract text and structured fields.

    Supported formats: JPEG, PNG.
    Maximum file size: 10 MB.
    Maximum image dimensions: 25 megapixels.

    The response includes:
      - Raw OCR text with per-line confidence.
      - Document-type classification.
      - Structured field extraction for supported document types.
      - Human verification requirement flag (always True).

    Extracted information is NEVER treated as verified identity data.
    A receptionist MUST review and confirm all extracted values.
    """
    settings = get_settings()
    start_time = time.monotonic()
    image_bytes = bytearray()

    try:
        # --- Read upload with size enforcement ---
        while True:
            remaining = MAX_IMAGE_SIZE + 1 - len(image_bytes)
            chunk = await file.read(min(CHUNK_SIZE, remaining))

            if not chunk:
                break

            image_bytes.extend(chunk)

            if len(image_bytes) > MAX_IMAGE_SIZE:
                raise HTTPException(
                    status_code=413,
                    detail="Uploaded file exceeds the 10 MB limit.",
                )

        # --- Validate image ---
        image_info = validate_image(bytes(image_bytes))

        # --- Concurrency gate ---
        acquired = await ocr_concurrency_limiter.acquire()
        if not acquired:
            raise HTTPException(
                status_code=503,
                detail="OCR service is busy. Please try again shortly.",
            )

        try:
            # --- OCR extraction ---
            ocr_result = await run_in_threadpool(
                ocr_service.extract, bytes(image_bytes)
            )

            # --- Document extraction ---
            ocr_lines = ocr_result.get("lines", [])
            extraction = document_extraction_service.extract(
                ocr_lines,
                document_type_hint=document_type,
            )

        finally:
            ocr_concurrency_limiter.release()

        elapsed_ms = round((time.monotonic() - start_time) * 1000, 1)

        return {
            "status": "success",
            "message": "Document text extracted successfully.",
            "document": {
                "format": image_info["format"],
                "width": image_info["width"],
                "height": image_info["height"],
            },
            "ocr_result": ocr_result,
            "extraction": extraction.model_dump(),
            "processing_time_ms": elapsed_ms,
            "verification_required": True,
        }

    except ImageValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    except HTTPException:
        raise

    except Exception:
        logger.exception("Document processing failed.")
        raise HTTPException(
            status_code=500,
            detail="Document processing failed.",
        )

    finally:
        image_bytes.clear()
        await file.close()
