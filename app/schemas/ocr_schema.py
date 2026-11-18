
from typing import Literal

from pydantic import BaseModel, Field


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
    verification_required: bool = True
