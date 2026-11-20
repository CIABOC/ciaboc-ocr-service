"""
Abstract base extractor for structured document field extraction.

Each document type (NIC, passport, driving licence) has its own
concrete extractor that inherits from this base class.
"""

from abc import ABC, abstractmethod
from typing import Any

from app.schemas.document_schema import DocumentExtractionResult


class BaseExtractor(ABC):
    """Abstract base class for document field extractors."""

    @abstractmethod
    def extract(
        self,
        ocr_lines: list[dict[str, Any]],
    ) -> DocumentExtractionResult:
        """
        Extract structured fields from raw OCR lines.

        Args:
            ocr_lines: List of dicts with 'text' and 'confidence' keys.

        Returns:
            DocumentExtractionResult with populated fields for the
            document type this extractor handles.
        """

    @staticmethod
    def _make_field(
        value: str | None,
        raw_text: str | None = None,
        confidence: float | None = None,
        needs_verification: bool = True,
    ) -> dict:
        """Helper to construct an ExtractedField dict."""
        return {
            "value": value,
            "raw_text": raw_text,
            "confidence": confidence,
            "needs_verification": needs_verification,
        }

    @staticmethod
    def _join_text(ocr_lines: list[dict[str, Any]]) -> str:
        """Join all OCR line texts into a single string."""
        return " ".join(line.get("text", "") for line in ocr_lines)

    @staticmethod
    def _raw_texts(ocr_lines: list[dict[str, Any]]) -> list[str]:
        """Extract raw text strings from OCR lines."""
        return [line.get("text", "") for line in ocr_lines]
