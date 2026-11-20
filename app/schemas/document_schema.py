"""
Document schemas for structured field extraction.

These schemas represent extracted identity document fields.
Extracted values are NEVER treated as verified identity information.
All extraction requires human verification by a receptionist.
"""

from typing import Optional, Literal
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Field-level extraction result
# ---------------------------------------------------------------------------

class ExtractedField(BaseModel):
    """A single extracted field with provenance information."""

    value: Optional[str] = Field(
        None,
        description="Normalized extracted value, or null if not extracted."
    )
    raw_text: Optional[str] = Field(
        None,
        description="Original OCR text before normalization."
    )
    confidence: Optional[float] = Field(
        None,
        ge=0.0, le=1.0,
        description="OCR confidence for this field, if available."
    )
    needs_verification: bool = Field(
        True,
        description="Whether this field requires human verification."
    )


# ---------------------------------------------------------------------------
# Document type classification
# ---------------------------------------------------------------------------

DocumentType = Literal["NIC", "PASSPORT", "DRIVING_LICENCE", "UNKNOWN"]


class DocumentClassification(BaseModel):
    """Result of document type detection."""

    document_type: DocumentType = "UNKNOWN"
    confidence: Optional[float] = Field(
        None,
        ge=0.0, le=1.0,
        description="Classification confidence."
    )
    evidence: list[str] = Field(
        default_factory=list,
        description="Evidence supporting the classification."
    )


# ---------------------------------------------------------------------------
# NIC extraction
# ---------------------------------------------------------------------------

class NICExtraction(BaseModel):
    """Extracted fields from a Sri Lankan National Identity Card."""

    nic_number: ExtractedField = Field(default_factory=ExtractedField)
    full_name: ExtractedField = Field(default_factory=ExtractedField)
    date_of_birth: ExtractedField = Field(default_factory=ExtractedField)
    gender: ExtractedField = Field(default_factory=ExtractedField)
    address: ExtractedField = Field(default_factory=ExtractedField)
    nic_format: Optional[str] = Field(
        None,
        description="Detected NIC format: 'old' (9 digits + V/X) or 'new' (12 digits)."
    )


# ---------------------------------------------------------------------------
# Passport extraction
# ---------------------------------------------------------------------------

class MRZData(BaseModel):
    """Machine Readable Zone extraction result."""

    raw_lines: list[str] = Field(
        default_factory=list,
        description="Raw MRZ text lines as read by OCR."
    )
    parsed_successfully: bool = False
    passport_number: Optional[str] = None
    nationality: Optional[str] = None
    date_of_birth: Optional[str] = None
    gender: Optional[str] = None
    expiry_date: Optional[str] = None
    surname: Optional[str] = None
    given_names: Optional[str] = None
    check_digits_valid: Optional[bool] = None


class PassportExtraction(BaseModel):
    """Extracted fields from a passport."""

    passport_number: ExtractedField = Field(default_factory=ExtractedField)
    full_name: ExtractedField = Field(default_factory=ExtractedField)
    date_of_birth: ExtractedField = Field(default_factory=ExtractedField)
    nationality: ExtractedField = Field(default_factory=ExtractedField)
    gender: ExtractedField = Field(default_factory=ExtractedField)
    expiry_date: ExtractedField = Field(default_factory=ExtractedField)
    mrz: Optional[MRZData] = None


# ---------------------------------------------------------------------------
# Driving licence extraction
# ---------------------------------------------------------------------------

class DrivingLicenceExtraction(BaseModel):
    """Extracted fields from a Sri Lankan driving licence."""

    licence_number: ExtractedField = Field(default_factory=ExtractedField)
    full_name: ExtractedField = Field(default_factory=ExtractedField)
    date_of_birth: ExtractedField = Field(default_factory=ExtractedField)
    address: ExtractedField = Field(default_factory=ExtractedField)
    expiry_date: ExtractedField = Field(default_factory=ExtractedField)
    categories: ExtractedField = Field(default_factory=ExtractedField)


# ---------------------------------------------------------------------------
# Unified extraction result
# ---------------------------------------------------------------------------

class DocumentExtractionResult(BaseModel):
    """Complete extraction result for any supported document type."""

    classification: DocumentClassification = Field(
        default_factory=DocumentClassification
    )
    nic: Optional[NICExtraction] = None
    passport: Optional[PassportExtraction] = None
    driving_licence: Optional[DrivingLicenceExtraction] = None
    raw_text: list[str] = Field(
        default_factory=list,
        description="All raw OCR text lines preserved."
    )
    extraction_notes: list[str] = Field(
        default_factory=list,
        description="Notes about extraction quality or limitations."
    )
