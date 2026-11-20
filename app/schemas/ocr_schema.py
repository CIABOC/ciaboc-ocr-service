"""
Pydantic response schemas for the OCR API.

These schemas define the HTTP response structure returned by the
/api/v1/ocr/extract endpoint.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.schemas.document_schema import DocumentExtractionResult


class DocumentInfo(BaseModel):
    """Information about the uploaded document image."""

    format: Literal["JPEG", "PNG"]
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class OCRLine(BaseModel):
    """A single line of text extracted by OCR."""

    text: str
    confidence: float = Field(ge=0.0, le=1.0)


class OCRResult(BaseModel):
    """OCR engine extraction results."""

    language: str
    lines: list[OCRLine]


class OCRResponse(BaseModel):
    """Standard response returned by the OCR API."""

    status: Literal["success"]
    message: str
    document: DocumentInfo
    ocr_result: OCRResult
    extraction: Optional[DocumentExtractionResult] = Field(
        None,
        description="Structured field extraction result, if available."
    )
    processing_time_ms: Optional[float] = Field(
        None,
        description="Processing time in milliseconds."
    )
    verification_required: bool = True
