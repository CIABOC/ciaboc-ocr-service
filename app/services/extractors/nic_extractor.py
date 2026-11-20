"""
Sri Lankan National Identity Card (NIC) field extractor.

Supports two NIC formats:
  - Old format: 9 digits followed by V or X (e.g. 912345678V)
  - New format: 12 digits (e.g. 200012345678)

Date of birth and gender can be derived from the NIC number itself
using well-known rules, but only when the format is reliably detected.

IMPORTANT: Extracted values are CANDIDATES only. They are never treated
as verified identity information and always require human verification.
"""

import re
from datetime import date, timedelta
from typing import Any

from app.services.extractors.base_extractor import BaseExtractor
from app.schemas.document_schema import (
    DocumentExtractionResult,
    DocumentClassification,
    NICExtraction,
    ExtractedField,
)

# ---------------------------------------------------------------------------
# NIC number patterns
# ---------------------------------------------------------------------------

# Old format: 9 digits + V or X (case-insensitive)
OLD_NIC_PATTERN = re.compile(r"\b(\d{9}[VvXx])\b")

# New format: exactly 12 digits
NEW_NIC_PATTERN = re.compile(r"\b(\d{12})\b")

# Common OCR confusions that might affect NIC numbers
OCR_DIGIT_CONFUSION: dict[str, str] = {
    "O": "0", "o": "0",
    "l": "1", "I": "1", "|": "1",
    "S": "5", "s": "5",
    "B": "8",
    "Z": "2", "z": "2",
    "G": "6",
}

# Name-related label patterns found on Sri Lankan NICs
NAME_LABEL_PATTERNS = [
    re.compile(r"(?:full\s*name|name)\s*[:\-]?\s*(.+)", re.IGNORECASE),
]

DOB_LABEL_PATTERNS = [
    re.compile(
        r"(?:date\s*of\s*birth|birth\s*date|d\.?o\.?b\.?)\s*[:\-]?\s*(.+)",
        re.IGNORECASE,
    ),
]

GENDER_LABEL_PATTERNS = [
    re.compile(r"(?:sex|gender)\s*[:\-]?\s*(male|female|m|f)", re.IGNORECASE),
]

ADDRESS_LABEL_PATTERNS = [
    re.compile(r"(?:address)\s*[:\-]?\s*(.+)", re.IGNORECASE),
]


class NICExtractor(BaseExtractor):
    """Extract structured fields from Sri Lankan NIC OCR text."""

    def extract(
        self,
        ocr_lines: list[dict[str, Any]],
    ) -> DocumentExtractionResult:
        raw_texts = self._raw_texts(ocr_lines)
        full_text = self._join_text(ocr_lines)
        notes: list[str] = []

        # --- NIC number ---
        nic_field, nic_format, nic_notes = self._extract_nic_number(
            ocr_lines, full_text
        )
        notes.extend(nic_notes)

        # --- Date of birth ---
        dob_field = self._extract_dob(ocr_lines, nic_field, nic_format)

        # --- Gender ---
        gender_field = self._extract_gender(ocr_lines, nic_field, nic_format)

        # --- Name ---
        name_field = self._extract_label_field(
            ocr_lines, NAME_LABEL_PATTERNS, "name"
        )

        # --- Address ---
        address_field = self._extract_label_field(
            ocr_lines, ADDRESS_LABEL_PATTERNS, "address"
        )

        nic_extraction = NICExtraction(
            nic_number=nic_field,
            full_name=name_field,
            date_of_birth=dob_field,
            gender=gender_field,
            address=address_field,
            nic_format=nic_format,
        )

        classification = DocumentClassification(
            document_type="NIC",
            confidence=None,
            evidence=["Extracted by NIC-specific extractor."],
        )

        return DocumentExtractionResult(
            classification=classification,
            nic=nic_extraction,
            raw_text=raw_texts,
            extraction_notes=notes,
        )

    # ------------------------------------------------------------------
    # NIC number extraction
    # ------------------------------------------------------------------

    def _extract_nic_number(
        self,
        ocr_lines: list[dict[str, Any]],
        full_text: str,
    ) -> tuple[ExtractedField, str | None, list[str]]:
        """
        Extract the NIC number candidate from OCR text.

        Returns (ExtractedField, format_str_or_None, notes).
        """
        notes: list[str] = []

        # Try old format first (more distinctive pattern)
        for line in ocr_lines:
            text = line.get("text", "")
            confidence = line.get("confidence")

            match = OLD_NIC_PATTERN.search(text)
            if match:
                raw = match.group(1)
                normalized = raw.upper()
                return (
                    ExtractedField(
                        value=normalized,
                        raw_text=raw,
                        confidence=confidence,
                        needs_verification=True,
                    ),
                    "old",
                    notes,
                )

        # Try new format
        for line in ocr_lines:
            text = line.get("text", "")
            confidence = line.get("confidence")

            match = NEW_NIC_PATTERN.search(text)
            if match:
                raw = match.group(1)
                return (
                    ExtractedField(
                        value=raw,
                        raw_text=raw,
                        confidence=confidence,
                        needs_verification=True,
                    ),
                    "new",
                    notes,
                )

        # Try with OCR confusion correction
        for line in ocr_lines:
            text = line.get("text", "")
            corrected = self._apply_ocr_corrections(text)
            confidence = line.get("confidence")

            match = OLD_NIC_PATTERN.search(corrected)
            if match:
                raw = match.group(1)
                notes.append(
                    "NIC number extracted after OCR character correction. "
                    "Original text preserved for verification."
                )
                return (
                    ExtractedField(
                        value=raw.upper(),
                        raw_text=text,
                        confidence=confidence,
                        needs_verification=True,
                    ),
                    "old",
                    notes,
                )

            match = NEW_NIC_PATTERN.search(corrected)
            if match:
                raw = match.group(1)
                notes.append(
                    "NIC number extracted after OCR character correction. "
                    "Original text preserved for verification."
                )
                return (
                    ExtractedField(
                        value=raw,
                        raw_text=text,
                        confidence=confidence,
                        needs_verification=True,
                    ),
                    "new",
                    notes,
                )

        notes.append("No NIC number candidate found in OCR text.")
        return (
            ExtractedField(value=None, needs_verification=True),
            None,
            notes,
        )

    # ------------------------------------------------------------------
    # Date of birth derivation from NIC number
    # ------------------------------------------------------------------

    def _extract_dob(
        self,
        ocr_lines: list[dict[str, Any]],
        nic_field: ExtractedField,
        nic_format: str | None,
    ) -> ExtractedField:
        """Extract date of birth from labels or derive from NIC number."""

        # First try explicit label on the document
        label_field = self._extract_label_field(
            ocr_lines, DOB_LABEL_PATTERNS, "date_of_birth"
        )
        if label_field.value is not None:
            return label_field

        # Derive from NIC number if possible
        if nic_field.value and nic_format:
            dob = self._dob_from_nic(nic_field.value, nic_format)
            if dob:
                return ExtractedField(
                    value=dob,
                    raw_text=nic_field.raw_text,
                    confidence=nic_field.confidence,
                    needs_verification=True,
                )

        return ExtractedField(value=None, needs_verification=True)

    def _dob_from_nic(
        self, nic_value: str, nic_format: str
    ) -> str | None:
        """
        Derive date of birth from NIC number using format rules.

        Old format (9 digits + V/X):
            - Digits 1-2: birth year (last two digits)
            - Digits 3-5: day of year (1-366 for male, 501-866 for female)

        New format (12 digits):
            - Digits 1-4: birth year
            - Digits 5-7: day of year (same male/female rule)

        Returns ISO date string or None if derivation is uncertain.
        """
        try:
            if nic_format == "old":
                year_part = int(nic_value[:2])
                day_of_year = int(nic_value[2:5])

                # Determine century: simple heuristic
                if year_part >= 0:
                    year = 1900 + year_part
                    # People born after 2000 with old NIC are unlikely
                    # but possible — flag for verification

            elif nic_format == "new":
                year = int(nic_value[:4])
                day_of_year = int(nic_value[4:7])
            else:
                return None

            # Adjust for female offset
            if day_of_year > 500:
                day_of_year -= 500

            if day_of_year < 1 or day_of_year > 366:
                return None

            # Convert day-of-year to date
            dob_date = date(year, 1, 1) + timedelta(days=day_of_year - 1)

            # Validate the date is reasonable
            if dob_date > date.today():
                return None

            return dob_date.isoformat()

        except (ValueError, OverflowError):
            return None

    # ------------------------------------------------------------------
    # Gender derivation from NIC number
    # ------------------------------------------------------------------

    def _extract_gender(
        self,
        ocr_lines: list[dict[str, Any]],
        nic_field: ExtractedField,
        nic_format: str | None,
    ) -> ExtractedField:
        """Extract gender from labels or derive from NIC number."""

        # First try explicit label
        label_field = self._extract_label_field(
            ocr_lines, GENDER_LABEL_PATTERNS, "gender"
        )
        if label_field.value is not None:
            return label_field

        # Derive from NIC number
        if nic_field.value and nic_format:
            gender = self._gender_from_nic(nic_field.value, nic_format)
            if gender:
                return ExtractedField(
                    value=gender,
                    raw_text=nic_field.raw_text,
                    confidence=nic_field.confidence,
                    needs_verification=True,
                )

        return ExtractedField(value=None, needs_verification=True)

    def _gender_from_nic(
        self, nic_value: str, nic_format: str
    ) -> str | None:
        """Derive gender from NIC number day-of-year encoding."""
        try:
            if nic_format == "old":
                day_of_year = int(nic_value[2:5])
            elif nic_format == "new":
                day_of_year = int(nic_value[4:7])
            else:
                return None

            if 1 <= day_of_year <= 366:
                return "Male"
            elif 501 <= day_of_year <= 866:
                return "Female"
            else:
                return None
        except (ValueError, IndexError):
            return None

    # ------------------------------------------------------------------
    # Generic label-based field extraction
    # ------------------------------------------------------------------

    def _extract_label_field(
        self,
        ocr_lines: list[dict[str, Any]],
        patterns: list[re.Pattern],
        field_name: str,
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

    # ------------------------------------------------------------------
    # OCR character correction
    # ------------------------------------------------------------------

    @staticmethod
    def _apply_ocr_corrections(text: str) -> str:
        """
        Apply common OCR character confusion corrections.

        Only used to find NIC number candidates — the original text
        is always preserved for human verification.
        """
        corrected = []
        for ch in text:
            corrected.append(OCR_DIGIT_CONFUSION.get(ch, ch))
        return "".join(corrected)
