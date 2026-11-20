"""
Sri Lankan driving licence field extractor.

Sri Lankan driving licences contain fields such as:
  - Licence number
  - Full name
  - Date of birth
  - Address
  - Expiry date
  - Vehicle categories

Document layouts vary. This extractor uses label-based pattern matching
and does NOT assume a fixed layout.

IMPORTANT: Extracted values are CANDIDATES only and require human
verification by a receptionist.
"""

import re
from typing import Any

from app.services.extractors.base_extractor import BaseExtractor
from app.schemas.document_schema import (
    DocumentExtractionResult,
    DocumentClassification,
    DrivingLicenceExtraction,
    ExtractedField,
)

# ---------------------------------------------------------------------------
# Field patterns for Sri Lankan driving licences
# ---------------------------------------------------------------------------

LICENCE_NO_PATTERNS = [
    re.compile(
        r"(?:licence\s*(?:no|number|#)|lic\s*(?:no|number|#)|dl\s*(?:no|number|#))"
        r"\s*[:\-]?\s*([A-Z0-9\-]{5,15})",
        re.IGNORECASE,
    ),
    # Common Sri Lankan DL format: letter(s) followed by digits
    re.compile(r"\b([A-Z]{1,2}\d{6,8})\b"),
]

NAME_PATTERNS = [
    re.compile(r"(?:full\s*name|name)\s*[:\-]?\s*(.+)", re.IGNORECASE),
    re.compile(r"(?:holder|driver)\s*[:\-]?\s*(.+)", re.IGNORECASE),
]

DOB_PATTERNS = [
    re.compile(
        r"(?:date\s*of\s*birth|birth\s*date|d\.?o\.?b\.?)\s*[:\-]?\s*(.+)",
        re.IGNORECASE,
    ),
]

ADDRESS_PATTERNS = [
    re.compile(r"(?:address)\s*[:\-]?\s*(.+)", re.IGNORECASE),
]

EXPIRY_PATTERNS = [
    re.compile(
        r"(?:date\s*of\s*expiry|expiry\s*date|exp\.?\s*date|valid\s*(?:until|till|to))"
        r"\s*[:\-]?\s*(.+)",
        re.IGNORECASE,
    ),
]

CATEGORY_PATTERNS = [
    re.compile(
        r"(?:categor(?:y|ies)|class|vehicle\s*class)\s*[:\-]?\s*(.+)",
        re.IGNORECASE,
    ),
    # Common Sri Lankan licence categories
    re.compile(r"\b([ABCDEGJH][1-4]?(?:\s*,\s*[ABCDEGJH][1-4]?)*)\b"),
]


class DrivingLicenceExtractor(BaseExtractor):
    """Extract structured fields from Sri Lankan driving licence OCR text."""

    def extract(
        self,
        ocr_lines: list[dict[str, Any]],
    ) -> DocumentExtractionResult:
        raw_texts = self._raw_texts(ocr_lines)
        notes: list[str] = []

        licence_number = self._search_labels(
            ocr_lines, LICENCE_NO_PATTERNS
        )
        full_name = self._search_labels(ocr_lines, NAME_PATTERNS)
        date_of_birth = self._search_labels(ocr_lines, DOB_PATTERNS)
        address = self._search_labels(ocr_lines, ADDRESS_PATTERNS)
        expiry_date = self._search_labels(ocr_lines, EXPIRY_PATTERNS)
        categories = self._search_labels(ocr_lines, CATEGORY_PATTERNS)

        # Note extraction limitations
        empty_fields = []
        if licence_number.value is None:
            empty_fields.append("licence number")
        if full_name.value is None:
            empty_fields.append("name")

        if empty_fields:
            notes.append(
                f"Could not extract: {', '.join(empty_fields)}. "
                "Document may have an unsupported layout or poor image quality."
            )

        dl_extraction = DrivingLicenceExtraction(
            licence_number=licence_number,
            full_name=full_name,
            date_of_birth=date_of_birth,
            address=address,
            expiry_date=expiry_date,
            categories=categories,
        )

        classification = DocumentClassification(
            document_type="DRIVING_LICENCE",
            confidence=None,
            evidence=["Extracted by driving-licence-specific extractor."],
        )

        return DocumentExtractionResult(
            classification=classification,
            driving_licence=dl_extraction,
            raw_text=raw_texts,
            extraction_notes=notes,
        )

    def _search_labels(
        self,
        ocr_lines: list[dict[str, Any]],
        patterns: list[re.Pattern],
    ) -> ExtractedField:
        """Search OCR lines for a labeled field value."""
        for line in ocr_lines:
            text = line.get("text", "")
            confidence = line.get("confidence")
            for pattern in patterns:
                match = pattern.search(text)
                if match:
                    value = match.group(1).strip()
                    if value:
                        return ExtractedField(
                            value=value,
                            raw_text=text,
                            confidence=confidence,
                            needs_verification=True,
                        )
        return ExtractedField(value=None, needs_verification=True)
