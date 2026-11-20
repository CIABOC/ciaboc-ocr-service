"""
Passport field extractor with MRZ (Machine Readable Zone) parsing.

Supports TD3 format passports (2 lines of 44 characters each).

MRZ check digit validation follows ICAO Doc 9303 Part 3.

IMPORTANT: Even if MRZ check digits pass, the extracted information
is still a CANDIDATE and requires human verification. Check digits
only validate internal MRZ consistency, not document authenticity.
"""

import re
from typing import Any

from app.services.extractors.base_extractor import BaseExtractor
from app.schemas.document_schema import (
    DocumentExtractionResult,
    DocumentClassification,
    PassportExtraction,
    MRZData,
    ExtractedField,
)


# MRZ character set: A-Z, 0-9, <
MRZ_LINE_PATTERN = re.compile(r"^[A-Z0-9<]{30,44}$")

# TD3 passport: exactly 2 lines of 44 characters
TD3_LINE_LENGTH = 44

# Check digit weights per ICAO 9303
MRZ_WEIGHTS = [7, 3, 1]

# MRZ character values
MRZ_CHAR_VALUES: dict[str, int] = {
    "<": 0, "0": 0, "1": 1, "2": 2, "3": 3, "4": 4,
    "5": 5, "6": 6, "7": 7, "8": 8, "9": 9,
}
for i, ch in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ", start=10):
    MRZ_CHAR_VALUES[ch] = i


# Label patterns for non-MRZ passport text
PASSPORT_NO_PATTERNS = [
    re.compile(
        r"(?:passport\s*(?:no|number|#))\s*[:\-]?\s*([A-Z0-9]{6,9})",
        re.IGNORECASE,
    ),
]

NAME_PATTERNS = [
    re.compile(r"(?:surname|family\s*name)\s*[:\-]?\s*(.+)", re.IGNORECASE),
    re.compile(r"(?:given\s*name|first\s*name)\s*[:\-]?\s*(.+)", re.IGNORECASE),
    re.compile(r"(?:full\s*name|name)\s*[:\-]?\s*(.+)", re.IGNORECASE),
]

DOB_PATTERNS = [
    re.compile(
        r"(?:date\s*of\s*birth|birth\s*date|d\.?o\.?b\.?)\s*[:\-]?\s*(.+)",
        re.IGNORECASE,
    ),
]

NATIONALITY_PATTERNS = [
    re.compile(r"(?:nationality)\s*[:\-]?\s*(.+)", re.IGNORECASE),
]

EXPIRY_PATTERNS = [
    re.compile(
        r"(?:date\s*of\s*expiry|expiry\s*date|exp\.?\s*date)\s*[:\-]?\s*(.+)",
        re.IGNORECASE,
    ),
]

GENDER_PATTERNS = [
    re.compile(r"(?:sex|gender)\s*[:\-]?\s*(male|female|m|f)", re.IGNORECASE),
]


class PassportExtractor(BaseExtractor):
    """Extract structured fields from passport OCR text."""

    def extract(
        self,
        ocr_lines: list[dict[str, Any]],
    ) -> DocumentExtractionResult:
        raw_texts = self._raw_texts(ocr_lines)
        notes: list[str] = []

        # Try MRZ extraction first
        mrz_data = self._extract_mrz(ocr_lines, notes)

        # Build extraction from MRZ or fallback to label matching
        extraction = self._build_extraction(ocr_lines, mrz_data, notes)

        classification = DocumentClassification(
            document_type="PASSPORT",
            confidence=None,
            evidence=["Extracted by passport-specific extractor."],
        )

        return DocumentExtractionResult(
            classification=classification,
            passport=extraction,
            raw_text=raw_texts,
            extraction_notes=notes,
        )

    # ------------------------------------------------------------------
    # MRZ detection and parsing
    # ------------------------------------------------------------------

    def _extract_mrz(
        self,
        ocr_lines: list[dict[str, Any]],
        notes: list[str],
    ) -> MRZData | None:
        """Detect and parse TD3 MRZ from OCR lines."""
        mrz_candidates: list[str] = []

        for line in ocr_lines:
            text = line.get("text", "").strip().upper().replace(" ", "")
            if MRZ_LINE_PATTERN.match(text) and len(text) >= 30:
                mrz_candidates.append(text)

        if len(mrz_candidates) < 2:
            return None

        # Find the best pair of TD3 lines (44 chars each)
        td3_lines: list[str] = []
        for candidate in mrz_candidates:
            if len(candidate) == TD3_LINE_LENGTH:
                td3_lines.append(candidate)

        if len(td3_lines) < 2:
            # Try with the longest candidates
            mrz_candidates.sort(key=len, reverse=True)
            mrz_data = MRZData(
                raw_lines=mrz_candidates[:2],
                parsed_successfully=False,
            )
            notes.append(
                "MRZ lines detected but do not match TD3 format "
                f"(expected {TD3_LINE_LENGTH} chars per line)."
            )
            return mrz_data

        # Take the last two TD3-length lines (MRZ is at the bottom)
        line1 = td3_lines[-2]
        line2 = td3_lines[-1]

        return self._parse_td3(line1, line2, notes)

    def _parse_td3(
        self, line1: str, line2: str, notes: list[str]
    ) -> MRZData:
        """
        Parse TD3 MRZ format (ICAO 9303 passport).

        Line 1 (44 chars):
            Pos 0:    Document type (P)
            Pos 1:    Type subtype
            Pos 2-4:  Issuing state (3-letter code)
            Pos 5-43: Surname << Given Names (< separated)

        Line 2 (44 chars):
            Pos 0-8:   Passport number
            Pos 9:     Check digit for passport number
            Pos 10-12: Nationality
            Pos 13-18: Date of birth (YYMMDD)
            Pos 19:    Check digit for DOB
            Pos 20:    Sex (M/F/<)
            Pos 21-26: Date of expiry (YYMMDD)
            Pos 27:    Check digit for expiry
            Pos 28-42: Optional data
            Pos 43:    Overall check digit
        """
        mrz_data = MRZData(
            raw_lines=[line1, line2],
            parsed_successfully=False,
        )

        try:
            # --- Line 1: Names ---
            name_section = line1[5:]
            parts = name_section.split("<<")
            surname = parts[0].replace("<", " ").strip() if parts else None
            given_names = (
                parts[1].replace("<", " ").strip()
                if len(parts) > 1 else None
            )

            mrz_data.surname = surname or None
            mrz_data.given_names = given_names or None

            # --- Line 2: Fields ---
            passport_number = line2[0:9].replace("<", "").strip()
            passport_check = line2[9]
            nationality = line2[10:13].replace("<", "").strip()
            dob_raw = line2[13:19]
            dob_check = line2[19]
            sex = line2[20]
            expiry_raw = line2[21:27]
            expiry_check = line2[27]

            mrz_data.passport_number = passport_number or None
            mrz_data.nationality = nationality or None
            mrz_data.gender = self._decode_sex(sex)

            # Validate check digits
            all_valid = True

            if not self._verify_check_digit(line2[0:9], passport_check):
                notes.append("MRZ passport number check digit is invalid.")
                all_valid = False

            if not self._verify_check_digit(dob_raw, dob_check):
                notes.append("MRZ date of birth check digit is invalid.")
                all_valid = False
            else:
                mrz_data.date_of_birth = self._decode_mrz_date(dob_raw)

            if not self._verify_check_digit(expiry_raw, expiry_check):
                notes.append("MRZ expiry date check digit is invalid.")
                all_valid = False
            else:
                mrz_data.expiry_date = self._decode_mrz_date(expiry_raw)

            mrz_data.check_digits_valid = all_valid
            mrz_data.parsed_successfully = True

        except (IndexError, ValueError) as exc:
            notes.append(f"MRZ parsing failed: {type(exc).__name__}")

        return mrz_data

    # ------------------------------------------------------------------
    # MRZ utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _verify_check_digit(data: str, check_char: str) -> bool:
        """Verify an MRZ check digit per ICAO 9303."""
        try:
            expected = int(check_char)
        except ValueError:
            return False

        total = 0
        for i, ch in enumerate(data):
            val = MRZ_CHAR_VALUES.get(ch)
            if val is None:
                return False
            total += val * MRZ_WEIGHTS[i % 3]

        return (total % 10) == expected

    @staticmethod
    def _decode_mrz_date(raw: str) -> str | None:
        """
        Decode YYMMDD MRZ date to ISO format.

        Uses a pivot: YY >= 50 → 19YY, YY < 50 → 20YY.
        """
        if len(raw) != 6 or not raw.isdigit():
            return None

        yy = int(raw[0:2])
        mm = raw[2:4]
        dd = raw[4:6]

        year = 1900 + yy if yy >= 50 else 2000 + yy

        return f"{year}-{mm}-{dd}"

    @staticmethod
    def _decode_sex(ch: str) -> str | None:
        mapping = {"M": "Male", "F": "Female", "<": None}
        return mapping.get(ch)

    # ------------------------------------------------------------------
    # Build extraction result
    # ------------------------------------------------------------------

    def _build_extraction(
        self,
        ocr_lines: list[dict[str, Any]],
        mrz_data: MRZData | None,
        notes: list[str],
    ) -> PassportExtraction:
        """Build PassportExtraction from MRZ and/or label matching."""

        extraction = PassportExtraction()

        if mrz_data and mrz_data.parsed_successfully:
            extraction.mrz = mrz_data

            if mrz_data.passport_number:
                extraction.passport_number = ExtractedField(
                    value=mrz_data.passport_number,
                    raw_text=mrz_data.raw_lines[1] if mrz_data.raw_lines else None,
                    confidence=None,
                    needs_verification=True,
                )

            if mrz_data.surname or mrz_data.given_names:
                parts = []
                if mrz_data.given_names:
                    parts.append(mrz_data.given_names)
                if mrz_data.surname:
                    parts.append(mrz_data.surname)
                extraction.full_name = ExtractedField(
                    value=" ".join(parts),
                    raw_text=mrz_data.raw_lines[0] if mrz_data.raw_lines else None,
                    confidence=None,
                    needs_verification=True,
                )

            if mrz_data.date_of_birth:
                extraction.date_of_birth = ExtractedField(
                    value=mrz_data.date_of_birth,
                    raw_text=mrz_data.raw_lines[1] if mrz_data.raw_lines else None,
                    confidence=None,
                    needs_verification=True,
                )

            if mrz_data.nationality:
                extraction.nationality = ExtractedField(
                    value=mrz_data.nationality,
                    raw_text=mrz_data.raw_lines[1] if mrz_data.raw_lines else None,
                    confidence=None,
                    needs_verification=True,
                )

            if mrz_data.gender:
                extraction.gender = ExtractedField(
                    value=mrz_data.gender,
                    raw_text=mrz_data.raw_lines[1] if mrz_data.raw_lines else None,
                    confidence=None,
                    needs_verification=True,
                )

            if mrz_data.expiry_date:
                extraction.expiry_date = ExtractedField(
                    value=mrz_data.expiry_date,
                    raw_text=mrz_data.raw_lines[1] if mrz_data.raw_lines else None,
                    confidence=None,
                    needs_verification=True,
                )
        else:
            if mrz_data:
                extraction.mrz = mrz_data

            # Fallback: label-based extraction
            extraction.passport_number = self._search_labels(
                ocr_lines, PASSPORT_NO_PATTERNS
            )
            extraction.full_name = self._search_labels(
                ocr_lines, NAME_PATTERNS
            )
            extraction.date_of_birth = self._search_labels(
                ocr_lines, DOB_PATTERNS
            )
            extraction.nationality = self._search_labels(
                ocr_lines, NATIONALITY_PATTERNS
            )
            extraction.gender = self._search_labels(
                ocr_lines, GENDER_PATTERNS
            )
            extraction.expiry_date = self._search_labels(
                ocr_lines, EXPIRY_PATTERNS
            )

            if not mrz_data:
                notes.append(
                    "No MRZ detected. Extraction based on text labels only."
                )

        return extraction

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
