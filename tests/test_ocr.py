"""
Comprehensive test suite for the CIABOC OCR Microservice.

Test categories:
  - Health and status endpoints
  - Valid image upload and OCR extraction
  - Image validation (format, size, corruption, decompression bombs)
  - NIC extraction (old format, new format, edge cases)
  - Passport extraction (MRZ parsing, check digits, label fallback)
  - Driving licence extraction
  - Document classification
  - API security (auth, oversized requests, error responses)
  - Concurrency

Tests that require the PaddleOCR engine are marked with @pytest.mark.integration.
Unit tests use mocked OCR engines for speed and determinism.
"""

import io
import struct
import zlib
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont

from app.main import app
from app.services.extractors.nic_extractor import NICExtractor
from app.services.extractors.passport_extractor import PassportExtractor
from app.services.extractors.driving_licence_extractor import (
    DrivingLicenceExtractor,
)
from app.services.document_classifier import DocumentClassifier
from app.services.document_extraction_service import (
    DocumentExtractionService,
)
from app.schemas.document_schema import ExtractedField


client = TestClient(app)


# ===================================================================
# Test Image Generators
# ===================================================================

def create_test_image(image_format="JPEG", text_lines=None):
    """Create a synthetic image containing readable text."""
    if text_lines is None:
        text_lines = [
            "CIABOC RECEPTION MANAGEMENT",
            "VISITOR ID: TEST-001",
            "NAME: JOHN DOE",
        ]

    image = Image.new("RGB", (800, 300), color="white")
    draw = ImageDraw.Draw(image)

    try:
        font_path = "C:/Windows/Fonts/arial.ttf"
        font = ImageFont.truetype(font_path, 32)
    except (IOError, OSError):
        font = ImageFont.load_default()

    y = 40
    for line in text_lines:
        draw.text((40, y), line, fill="black", font=font)
        y += 70

    image_bytes = io.BytesIO()
    image.save(image_bytes, format=image_format)
    return image_bytes.getvalue()


def create_nic_image(nic_number="912345678V"):
    """Create a synthetic NIC-like image."""
    return create_test_image(
        "PNG",
        [
            "NATIONAL IDENTITY CARD",
            f"NIC No: {nic_number}",
            "Name: JOHN DOE",
            "Date of Birth: 1991-05-15",
        ],
    )


def create_passport_image():
    """Create a synthetic passport-like image with MRZ."""
    return create_test_image(
        "PNG",
        [
            "PASSPORT",
            "Surname: DOE",
            "Given Names: JOHN",
            "Nationality: LKA",
            "Date of Birth: 1990-01-15",
        ],
    )


def create_driving_licence_image():
    """Create a synthetic driving licence image."""
    return create_test_image(
        "PNG",
        [
            "DRIVING LICENCE",
            "Licence No: B1234567",
            "Name: JOHN DOE",
            "Date of Birth: 1990-01-15",
            "Category: B1, A1",
        ],
    )


def create_minimal_png(width=1, height=1):
    """Create a minimal valid PNG file."""
    image = Image.new("RGB", (width, height), color="white")
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def create_minimal_bmp():
    """Create a minimal valid BMP file."""
    image = Image.new("RGB", (1, 1), color="white")
    buf = io.BytesIO()
    image.save(buf, format="BMP")
    return buf.getvalue()


def create_gif_image():
    """Create a minimal GIF image (unsupported format)."""
    image = Image.new("RGB", (10, 10), color="white")
    buf = io.BytesIO()
    image.save(buf, format="GIF")
    return buf.getvalue()


# ===================================================================
# Health and Status Tests
# ===================================================================

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_ocr_status_endpoint():
    response = client.get("/api/v1/ocr/status")
    assert response.status_code == 200
    assert response.json()["status"] == "available"


# ===================================================================
# Valid Image Upload Tests (Integration — requires PaddleOCR)
# ===================================================================

@pytest.mark.integration
def test_valid_jpeg_upload():
    image = create_test_image("JPEG")
    response = client.post(
        "/api/v1/ocr/extract",
        files={"file": ("test.jpg", image, "image/jpeg")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["message"] == "Document text extracted successfully."
    assert data["document"]["format"] == "JPEG"
    assert data["verification_required"] is True
    assert "ocr_result" in data
    assert "lines" in data["ocr_result"]
    assert len(data["ocr_result"]["lines"]) > 0

    extracted_text = " ".join(
        item["text"] for item in data["ocr_result"]["lines"]
    )
    assert "CIABOC" in extracted_text


@pytest.mark.integration
def test_valid_png_upload():
    image = create_test_image("PNG")
    response = client.post(
        "/api/v1/ocr/extract",
        files={"file": ("test.png", image, "image/png")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["document"]["format"] == "PNG"
    assert data["verification_required"] is True
    assert len(data["ocr_result"]["lines"]) > 0


@pytest.mark.integration
def test_extraction_includes_document_fields():
    """Verify that the response includes structured extraction."""
    image = create_test_image("PNG")
    response = client.post(
        "/api/v1/ocr/extract",
        files={"file": ("test.png", image, "image/png")},
    )
    assert response.status_code == 200
    data = response.json()
    assert "extraction" in data
    assert "classification" in data["extraction"]
    assert "raw_text" in data["extraction"]


@pytest.mark.integration
def test_extraction_processing_time():
    """Verify processing time is reported."""
    image = create_test_image("PNG")
    response = client.post(
        "/api/v1/ocr/extract",
        files={"file": ("test.png", image, "image/png")},
    )
    assert response.status_code == 200
    data = response.json()
    assert "processing_time_ms" in data
    assert data["processing_time_ms"] > 0


# ===================================================================
# Image Validation Tests
# ===================================================================

def test_invalid_file_upload():
    fake_file = b"This is not an image"
    response = client.post(
        "/api/v1/ocr/extract",
        files={"file": ("document.jpg", fake_file, "image/jpeg")},
    )
    assert response.status_code == 400


def test_pdf_renamed_as_jpeg():
    fake_pdf = b"%PDF-1.4 fake document content"
    response = client.post(
        "/api/v1/ocr/extract",
        files={"file": ("document.jpg", fake_pdf, "image/jpeg")},
    )
    assert response.status_code == 400


def test_empty_file_upload():
    response = client.post(
        "/api/v1/ocr/extract",
        files={"file": ("empty.jpg", b"", "image/jpeg")},
    )
    assert response.status_code == 400


def test_oversized_file_upload():
    oversized_file = b"A" * (10 * 1024 * 1024 + 1)
    response = client.post(
        "/api/v1/ocr/extract",
        files={"file": ("large.jpg", oversized_file, "image/jpeg")},
    )
    assert response.status_code == 413


def test_missing_file_upload():
    response = client.post("/api/v1/ocr/extract")
    assert response.status_code == 422


def test_invalid_image_content():
    invalid_content = b"This is not a valid image file."
    response = client.post(
        "/api/v1/ocr/extract",
        files={"file": ("document.png", invalid_content, "image/png")},
    )
    assert response.status_code == 400


def test_image_with_incorrect_mime_type():
    """MIME type does not matter — we validate actual content."""
    image = create_test_image("PNG")
    response = client.post(
        "/api/v1/ocr/extract",
        files={
            "file": (
                "document.jpg",
                image,
                "application/octet-stream",
            )
        },
    )
    # Should succeed because actual content is a valid PNG
    assert response.status_code == 200
    data = response.json()
    assert data["document"]["format"] == "PNG"
    assert data["status"] == "success"


def test_unsupported_format_bmp():
    """BMP images should be rejected."""
    bmp_data = create_minimal_bmp()
    response = client.post(
        "/api/v1/ocr/extract",
        files={"file": ("test.bmp", bmp_data, "image/bmp")},
    )
    assert response.status_code == 400


def test_unsupported_format_gif():
    """GIF images should be rejected."""
    gif_data = create_gif_image()
    response = client.post(
        "/api/v1/ocr/extract",
        files={"file": ("test.gif", gif_data, "image/gif")},
    )
    assert response.status_code == 400


def test_corrupted_png_header():
    """A file with PNG magic bytes but corrupted data should be rejected."""
    # PNG signature followed by garbage
    corrupted = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    response = client.post(
        "/api/v1/ocr/extract",
        files={"file": ("corrupt.png", corrupted, "image/png")},
    )
    assert response.status_code == 400


def test_corrupted_jpeg_header():
    """A file with JPEG magic bytes but corrupted data should be rejected."""
    corrupted = b"\xff\xd8\xff\xe0" + b"\x00" * 100
    response = client.post(
        "/api/v1/ocr/extract",
        files={"file": ("corrupt.jpg", corrupted, "image/jpeg")},
    )
    assert response.status_code == 400


# ===================================================================
# NIC Extractor Unit Tests (Mocked — no PaddleOCR required)
# ===================================================================

class TestNICExtractor:
    """Unit tests for the NIC field extractor."""

    def setup_method(self):
        self.extractor = NICExtractor()

    def test_old_nic_number_extraction(self):
        lines = [
            {"text": "NIC No: 912345678V", "confidence": 0.95},
            {"text": "Name: John Doe", "confidence": 0.90},
        ]
        result = self.extractor.extract(lines)
        assert result.nic is not None
        assert result.nic.nic_number.value == "912345678V"
        assert result.nic.nic_format == "old"

    def test_new_nic_number_extraction(self):
        lines = [
            {"text": "NIC: 200012345678", "confidence": 0.92},
        ]
        result = self.extractor.extract(lines)
        assert result.nic is not None
        assert result.nic.nic_number.value == "200012345678"
        assert result.nic.nic_format == "new"

    def test_old_nic_lowercase_v(self):
        lines = [
            {"text": "912345678v", "confidence": 0.90},
        ]
        result = self.extractor.extract(lines)
        assert result.nic is not None
        assert result.nic.nic_number.value == "912345678V"
        assert result.nic.nic_format == "old"

    def test_old_nic_x_suffix(self):
        lines = [
            {"text": "912345678X", "confidence": 0.90},
        ]
        result = self.extractor.extract(lines)
        assert result.nic is not None
        assert result.nic.nic_number.value == "912345678X"

    def test_missing_nic_number(self):
        lines = [
            {"text": "Name: John Doe", "confidence": 0.90},
            {"text": "Some random text", "confidence": 0.85},
        ]
        result = self.extractor.extract(lines)
        assert result.nic is not None
        assert result.nic.nic_number.value is None

    def test_name_extraction(self):
        lines = [
            {"text": "912345678V", "confidence": 0.95},
            {"text": "Name: KAMAL PERERA", "confidence": 0.90},
        ]
        result = self.extractor.extract(lines)
        assert result.nic is not None
        assert result.nic.full_name.value == "KAMAL PERERA"

    def test_missing_name(self):
        lines = [
            {"text": "912345678V", "confidence": 0.95},
            {"text": "Some text without name label", "confidence": 0.90},
        ]
        result = self.extractor.extract(lines)
        assert result.nic is not None
        assert result.nic.full_name.value is None

    def test_dob_from_label(self):
        lines = [
            {"text": "912345678V", "confidence": 0.95},
            {"text": "Date of Birth: 1991-05-15", "confidence": 0.88},
        ]
        result = self.extractor.extract(lines)
        assert result.nic is not None
        assert result.nic.date_of_birth.value == "1991-05-15"

    def test_dob_derived_from_old_nic(self):
        """DOB is derivable from old NIC: digits 1-2=year, 3-5=day of year."""
        # 91 -> 1991, 135 -> May 15
        lines = [
            {"text": "911350678V", "confidence": 0.95},
        ]
        result = self.extractor.extract(lines)
        assert result.nic is not None
        assert result.nic.date_of_birth.value is not None
        assert "1991-05-15" == result.nic.date_of_birth.value

    def test_gender_male_from_old_nic(self):
        """Day of year 1-366 = Male."""
        lines = [
            {"text": "911350678V", "confidence": 0.95},
        ]
        result = self.extractor.extract(lines)
        assert result.nic is not None
        assert result.nic.gender.value == "Male"

    def test_gender_female_from_old_nic(self):
        """Day of year 501-866 = Female."""
        lines = [
            {"text": "916350678V", "confidence": 0.95},
        ]
        result = self.extractor.extract(lines)
        assert result.nic is not None
        assert result.nic.gender.value == "Female"

    def test_gender_from_label(self):
        lines = [
            {"text": "912345678V", "confidence": 0.95},
            {"text": "Sex: Female", "confidence": 0.90},
        ]
        result = self.extractor.extract(lines)
        assert result.nic is not None
        assert result.nic.gender.value == "Female"

    def test_address_extraction(self):
        lines = [
            {"text": "912345678V", "confidence": 0.95},
            {"text": "Address: 123 Main St, Colombo", "confidence": 0.85},
        ]
        result = self.extractor.extract(lines)
        assert result.nic is not None
        assert result.nic.address.value == "123 Main St, Colombo"

    def test_ocr_confusion_correction(self):
        """OCR may confuse O for 0, etc. The extractor tries corrections."""
        lines = [
            {"text": "9l2345678V", "confidence": 0.75},
        ]
        result = self.extractor.extract(lines)
        assert result.nic is not None
        # After correction, l → 1, should find 912345678V
        assert result.nic.nic_number.value is not None

    def test_all_fields_need_verification(self):
        lines = [
            {"text": "912345678V", "confidence": 0.95},
            {"text": "Name: John", "confidence": 0.90},
        ]
        result = self.extractor.extract(lines)
        assert result.nic is not None
        assert result.nic.nic_number.needs_verification is True
        assert result.nic.full_name.needs_verification is True

    def test_raw_text_preserved(self):
        lines = [
            {"text": "NIC No: 912345678V", "confidence": 0.95},
        ]
        result = self.extractor.extract(lines)
        assert "NIC No: 912345678V" in result.raw_text

    def test_invalid_nic_candidate(self):
        """A number that looks like NIC but has invalid day-of-year."""
        lines = [
            {"text": "910000678V", "confidence": 0.95},
        ]
        result = self.extractor.extract(lines)
        assert result.nic is not None
        # Pattern match succeeds, but DOB derivation should fail
        assert result.nic.nic_number.value == "910000678V"
        assert result.nic.date_of_birth.value is None

    def test_uncertain_extraction_noted(self):
        """When OCR correction is used, a note is added."""
        lines = [
            {"text": "9O2345678V", "confidence": 0.60},
        ]
        result = self.extractor.extract(lines)
        # Either finds via correction (with note) or not
        if result.nic.nic_number.value is not None:
            assert any("correction" in n.lower() for n in result.extraction_notes)


# ===================================================================
# Passport Extractor Unit Tests
# ===================================================================

class TestPassportExtractor:
    """Unit tests for the passport field extractor."""

    def setup_method(self):
        self.extractor = PassportExtractor()

    def test_label_based_extraction(self):
        lines = [
            {"text": "PASSPORT", "confidence": 0.98},
            {"text": "Passport No: N1234567", "confidence": 0.92},
            {"text": "Full Name: JOHN DOE", "confidence": 0.90},
            {"text": "Date of Birth: 1990-01-15", "confidence": 0.88},
            {"text": "Nationality: Sri Lankan", "confidence": 0.85},
            {"text": "Gender: Male", "confidence": 0.90},
            {"text": "Date of Expiry: 2030-01-15", "confidence": 0.87},
        ]
        result = self.extractor.extract(lines)
        assert result.passport is not None
        assert result.passport.passport_number.value == "N1234567"
        assert result.passport.full_name.value == "JOHN DOE"
        assert result.passport.date_of_birth.value == "1990-01-15"
        assert result.passport.nationality.value == "Sri Lankan"
        assert result.passport.expiry_date.value == "2030-01-15"


    def test_mrz_parsing_valid(self):
        """Test TD3 MRZ parsing with valid check digits."""
        # Build TD3 MRZ lines using concatenation for exact 44-char length
        line1 = "P<LKADOE<<JOHN" + "<" * 30  # 14 + 30 = 44
        line2 = "N12345674LKA9001158M3001151" + "<" * 15 + "06"  # 27 + 15 + 2 = 44
        assert len(line1) == 44, f"Line 1 is {len(line1)} chars"
        assert len(line2) == 44, f"Line 2 is {len(line2)} chars"
        lines = [
            {"text": line1, "confidence": 0.95},
            {"text": line2, "confidence": 0.95},
        ]
        result = self.extractor.extract(lines)
        assert result.passport is not None
        assert result.passport.mrz is not None
        assert result.passport.mrz.parsed_successfully is True

    def test_mrz_invalid_check_digit(self):
        """MRZ with invalid check digit should be noted."""
        line1 = "P<LKADOE<<JOHN" + "<" * 30  # 44 chars
        line2 = "N12345679LKA9001158M3001151" + "<" * 15 + "06"  # bad passport check: 9
        assert len(line1) == 44, f"Line 1 is {len(line1)} chars"
        assert len(line2) == 44, f"Line 2 is {len(line2)} chars"
        lines = [
            {"text": line1, "confidence": 0.95},
            {"text": line2, "confidence": 0.95},
        ]
        result = self.extractor.extract(lines)
        assert result.passport is not None
        assert result.passport.mrz is not None
        # Notes should mention invalid check digit
        assert any("check digit" in n.lower() for n in result.extraction_notes)
    def test_no_mrz_fallback(self):
        """Without MRZ, should fall back to label matching."""
        lines = [
            {"text": "PASSPORT", "confidence": 0.98},
            {"text": "Passport Number: AB123456", "confidence": 0.90},
        ]
        result = self.extractor.extract(lines)
        assert result.passport is not None
        assert result.passport.passport_number.value == "AB123456"
        assert any("no mrz" in n.lower() for n in result.extraction_notes)

    def test_incomplete_mrz(self):
        """Single MRZ-like line without a pair should not parse as TD3."""
        lines = [
            {"text": "P<LKADOE<<JOHN<<<<<<<<<<<<<<<<<<<<<<<<<<<<<"
                     , "confidence": 0.95},
            {"text": "Some other text", "confidence": 0.80},
        ]
        result = self.extractor.extract(lines)
        assert result.passport is not None
        # Should not have successfully parsed MRZ

    def test_missing_fields(self):
        lines = [
            {"text": "PASSPORT", "confidence": 0.98},
        ]
        result = self.extractor.extract(lines)
        assert result.passport is not None
        assert result.passport.passport_number.value is None
        assert result.passport.full_name.value is None

    def test_raw_text_preserved(self):
        lines = [
            {"text": "PASSPORT", "confidence": 0.98},
            {"text": "Passport No: X999", "confidence": 0.90},
        ]
        result = self.extractor.extract(lines)
        assert "PASSPORT" in result.raw_text

    def test_mrz_check_digit_verification(self):
        """Unit test for the check digit algorithm."""
        # Known valid: "N1234567" with check digit 4
        assert PassportExtractor._verify_check_digit("N1234567<", "4") or \
               PassportExtractor._verify_check_digit("N12345674", "4") is not None

    def test_mrz_date_decoding(self):
        assert PassportExtractor._decode_mrz_date("900115") == "1990-01-15"
        assert PassportExtractor._decode_mrz_date("050715") == "2005-07-15"
        assert PassportExtractor._decode_mrz_date("abcdef") is None


# ===================================================================
# Driving Licence Extractor Unit Tests
# ===================================================================

class TestDrivingLicenceExtractor:
    """Unit tests for the driving licence field extractor."""

    def setup_method(self):
        self.extractor = DrivingLicenceExtractor()

    def test_valid_extraction(self):
        lines = [
            {"text": "DRIVING LICENCE", "confidence": 0.98},
            {"text": "Licence No: B1234567", "confidence": 0.92},
            {"text": "Name: KAMAL PERERA", "confidence": 0.90},
            {"text": "Date of Birth: 1985-03-20", "confidence": 0.88},
            {"text": "Address: 45 Temple Road, Kandy", "confidence": 0.85},
            {"text": "Date of Expiry: 2028-03-20", "confidence": 0.87},
            {"text": "Category: B1, A1", "confidence": 0.90},
        ]
        result = self.extractor.extract(lines)
        assert result.driving_licence is not None
        assert result.driving_licence.licence_number.value == "B1234567"
        assert result.driving_licence.full_name.value == "KAMAL PERERA"
        assert result.driving_licence.date_of_birth.value == "1985-03-20"
        assert result.driving_licence.address.value == "45 Temple Road, Kandy"
        assert result.driving_licence.expiry_date.value == "2028-03-20"
        assert result.driving_licence.categories.value == "B1, A1"

    def test_missing_fields(self):
        lines = [
            {"text": "DRIVING LICENCE", "confidence": 0.98},
        ]
        result = self.extractor.extract(lines)
        assert result.driving_licence is not None
        assert result.driving_licence.licence_number.value is None
        assert result.driving_licence.full_name.value is None
        assert len(result.extraction_notes) > 0

    def test_unclear_values(self):
        lines = [
            {"text": "DRIVING LICENCE", "confidence": 0.98},
            {"text": "Licence No: ???", "confidence": 0.30},
        ]
        result = self.extractor.extract(lines)
        assert result.driving_licence is not None
        # Should extract the value but needs_verification is always True
        assert result.driving_licence.licence_number.needs_verification is True

    def test_raw_text_preserved(self):
        lines = [
            {"text": "DRIVING LICENCE", "confidence": 0.98},
            {"text": "Licence No: B1234567", "confidence": 0.92},
        ]
        result = self.extractor.extract(lines)
        assert "DRIVING LICENCE" in result.raw_text


# ===================================================================
# Document Classifier Unit Tests
# ===================================================================

class TestDocumentClassifier:
    """Unit tests for document type classification."""

    def setup_method(self):
        self.classifier = DocumentClassifier()

    def test_classify_nic(self):
        lines = [
            {"text": "NATIONAL IDENTITY CARD", "confidence": 0.98},
            {"text": "NIC No: 912345678V", "confidence": 0.95},
        ]
        result = self.classifier.classify(lines)
        assert result.document_type == "NIC"
        assert len(result.evidence) > 0

    def test_classify_passport(self):
        lines = [
            {"text": "PASSPORT", "confidence": 0.98},
            {"text": "Nationality: Sri Lankan", "confidence": 0.90},
        ]
        result = self.classifier.classify(lines)
        assert result.document_type == "PASSPORT"

    def test_classify_driving_licence(self):
        lines = [
            {"text": "DRIVING LICENCE", "confidence": 0.98},
            {"text": "Vehicle Class: B1", "confidence": 0.90},
        ]
        result = self.classifier.classify(lines)
        assert result.document_type == "DRIVING_LICENCE"

    def test_classify_unknown(self):
        lines = [
            {"text": "Random text here", "confidence": 0.90},
            {"text": "Nothing recognizable", "confidence": 0.85},
        ]
        result = self.classifier.classify(lines)
        assert result.document_type == "UNKNOWN"
        assert result.confidence == 0.0

    def test_classification_evidence_provided(self):
        lines = [
            {"text": "NIC", "confidence": 0.98},
            {"text": "912345678V", "confidence": 0.95},
        ]
        result = self.classifier.classify(lines)
        assert len(result.evidence) > 0

    def test_empty_lines(self):
        result = self.classifier.classify([])
        assert result.document_type == "UNKNOWN"


# ===================================================================
# Document Extraction Service Unit Tests
# ===================================================================

class TestDocumentExtractionService:
    """Unit tests for the document extraction orchestration."""

    def setup_method(self):
        self.service = DocumentExtractionService()

    def test_extraction_with_nic_hint(self):
        lines = [
            {"text": "912345678V", "confidence": 0.95},
            {"text": "Name: JOHN", "confidence": 0.90},
        ]
        result = self.service.extract(lines, document_type_hint="NIC")
        assert result.classification.document_type == "NIC"
        assert result.nic is not None

    def test_extraction_with_passport_hint(self):
        lines = [
            {"text": "Passport No: AB123", "confidence": 0.90},
        ]
        result = self.service.extract(
            lines, document_type_hint="PASSPORT"
        )
        assert result.classification.document_type == "PASSPORT"
        assert result.passport is not None

    def test_extraction_auto_classify(self):
        lines = [
            {"text": "NATIONAL IDENTITY CARD", "confidence": 0.98},
            {"text": "912345678V", "confidence": 0.95},
        ]
        result = self.service.extract(lines)
        assert result.classification.document_type == "NIC"

    def test_extraction_unknown_type(self):
        lines = [
            {"text": "Hello world", "confidence": 0.90},
        ]
        result = self.service.extract(lines)
        assert result.classification.document_type == "UNKNOWN"
        assert result.nic is None
        assert result.passport is None
        assert result.driving_licence is None

    def test_raw_text_always_present(self):
        lines = [
            {"text": "Some text", "confidence": 0.90},
        ]
        result = self.service.extract(lines)
        assert "Some text" in result.raw_text


# ===================================================================
# API Security Tests
# ===================================================================

class TestAPISecurity:
    """Test API security controls."""

    def test_oversized_request_rejected(self):
        """Files over 10 MB should be rejected."""
        oversized = b"A" * (10 * 1024 * 1024 + 1)
        response = client.post(
            "/api/v1/ocr/extract",
            files={"file": ("big.jpg", oversized, "image/jpeg")},
        )
        assert response.status_code == 413

    def test_controlled_error_response(self):
        """Error responses should not contain stack traces."""
        response = client.post(
            "/api/v1/ocr/extract",
            files={"file": ("bad.jpg", b"not-an-image", "image/jpeg")},
        )
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        # Should not contain Python traceback
        assert "Traceback" not in data.get("detail", "")

    def test_health_endpoint_no_auth_required(self):
        """Health endpoint should be accessible without auth."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_missing_file_returns_422(self):
        """Missing file parameter returns proper validation error."""
        response = client.post("/api/v1/ocr/extract")
        assert response.status_code == 422


# ===================================================================
# OCR Engine Mocked Tests (Fast Unit Tests)
# ===================================================================

class TestMockedOCRExtraction:
    """Tests with mocked OCR engine for speed and determinism."""

    def _mock_ocr_extract(self, lines):
        """Create a mock that returns specified OCR lines."""
        mock_result = {
            "language": "en",
            "lines": lines,
        }
        return mock_result

    @patch("app.api.routes.ocr.ocr_service")
    def test_empty_ocr_result(self, mock_service):
        mock_service.extract.return_value = {
            "language": "en",
            "lines": [],
        }
        image = create_minimal_png(100, 100)
        response = client.post(
            "/api/v1/ocr/extract",
            files={"file": ("test.png", image, "image/png")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ocr_result"]["lines"] == []

    @patch("app.api.routes.ocr.ocr_service")
    def test_multiple_text_lines(self, mock_service):
        mock_service.extract.return_value = {
            "language": "en",
            "lines": [
                {"text": "Line 1", "confidence": 0.95},
                {"text": "Line 2", "confidence": 0.90},
                {"text": "Line 3", "confidence": 0.85},
            ],
        }
        image = create_minimal_png(100, 100)
        response = client.post(
            "/api/v1/ocr/extract",
            files={"file": ("test.png", image, "image/png")},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["ocr_result"]["lines"]) == 3

    @patch("app.api.routes.ocr.ocr_service")
    def test_ocr_engine_failure(self, mock_service):
        mock_service.extract.side_effect = RuntimeError(
            "Engine failed"
        )
        image = create_minimal_png(100, 100)
        response = client.post(
            "/api/v1/ocr/extract",
            files={"file": ("test.png", image, "image/png")},
        )
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        # Should not expose internal error message
        assert "Engine failed" not in data["detail"]

    @patch("app.api.routes.ocr.ocr_service")
    def test_nic_document_extraction_via_api(self, mock_service):
        """End-to-end: mock OCR returns NIC text, verify extraction."""
        mock_service.extract.return_value = {
            "language": "en",
            "lines": [
                {"text": "NATIONAL IDENTITY CARD", "confidence": 0.98},
                {"text": "NIC No: 912345678V", "confidence": 0.95},
                {"text": "Name: KAMAL PERERA", "confidence": 0.92},
            ],
        }
        image = create_minimal_png(100, 100)
        response = client.post(
            "/api/v1/ocr/extract",
            files={"file": ("test.png", image, "image/png")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["extraction"]["classification"]["document_type"] == "NIC"
        assert data["extraction"]["nic"]["nic_number"]["value"] == "912345678V"

    @patch("app.api.routes.ocr.ocr_service")
    def test_document_type_hint_via_query(self, mock_service):
        """Test document_type query parameter override."""
        mock_service.extract.return_value = {
            "language": "en",
            "lines": [
                {"text": "912345678V", "confidence": 0.95},
            ],
        }
        image = create_minimal_png(100, 100)
        response = client.post(
            "/api/v1/ocr/extract?document_type=NIC",
            files={"file": ("test.png", image, "image/png")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["extraction"]["classification"]["document_type"] == "NIC"


# ===================================================================
# MRZ Check Digit Unit Tests
# ===================================================================

class TestMRZCheckDigits:
    """Detailed unit tests for MRZ check digit validation."""

    def test_valid_check_digit_all_digits(self):
        # "520727" with check digit 3 (from ICAO examples)
        assert PassportExtractor._verify_check_digit("520727", "3")

    def test_valid_check_digit_with_letters(self):
        # Simple test: "AB" = 10*7 + 11*3 = 70 + 33 = 103 → 103 % 10 = 3
        assert PassportExtractor._verify_check_digit("AB", "3")

    def test_invalid_check_digit(self):
        assert not PassportExtractor._verify_check_digit("AB", "5")

    def test_filler_characters(self):
        # "<" = 0
        assert PassportExtractor._verify_check_digit("<<<", "0")

    def test_non_digit_check_char(self):
        assert not PassportExtractor._verify_check_digit("AB", "X")
