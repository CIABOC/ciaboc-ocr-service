
import io

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont

from app.main import app


client = TestClient(app)


# --------------------------------------------------
# Test Image Generator
# --------------------------------------------------

def create_test_image(image_format="JPEG"):
    """Create a synthetic image containing readable text."""

    image = Image.new("RGB", (800, 300), color="white")
    draw = ImageDraw.Draw(image)

    font_path = "C:/Windows/Fonts/arial.ttf"
    font = ImageFont.truetype(font_path, 32)

    draw.text(
        (40, 40),
        "CIABOC RECEPTION MANAGEMENT",
        fill="black",
        font=font
    )

    draw.text(
        (40, 110),
        "VISITOR ID: TEST-001",
        fill="black",
        font=font
    )

    draw.text(
        (40, 180),
        "NAME: JOHN DOE",
        fill="black",
        font=font
    )

    image_bytes = io.BytesIO()
    image.save(image_bytes, format=image_format)

    return image_bytes.getvalue()


# --------------------------------------------------
# Health and Status Tests
# --------------------------------------------------

def test_health_endpoint():

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_ocr_status_endpoint():

    response = client.get("/api/v1/ocr/status")

    assert response.status_code == 200
    assert response.json()["status"] == "available"


# --------------------------------------------------
# Valid Image Upload Tests
# --------------------------------------------------

def test_valid_jpeg_upload():

    image = create_test_image("JPEG")

    response = client.post(
        "/api/v1/ocr/extract",
        files={
            "file": ("test.jpg", image, "image/jpeg")
        }
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
    assert "TEST-001" in extracted_text


def test_valid_png_upload():

    image = create_test_image("PNG")

    response = client.post(
        "/api/v1/ocr/extract",
        files={
            "file": ("test.png", image, "image/png")
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "success"
    assert data["document"]["format"] == "PNG"
    assert data["verification_required"] is True

    assert len(data["ocr_result"]["lines"]) > 0


# --------------------------------------------------
# Invalid File Tests
# --------------------------------------------------

def test_invalid_file_upload():

    fake_file = b"This is not an image"

    response = client.post(
        "/api/v1/ocr/extract",
        files={
            "file": ("document.jpg", fake_file, "image/jpeg")
        }
    )

    assert response.status_code == 400


def test_pdf_renamed_as_jpeg():

    fake_pdf = b"%PDF-1.4 fake document content"

    response = client.post(
        "/api/v1/ocr/extract",
        files={
            "file": ("document.jpg", fake_pdf, "image/jpeg")
        }
    )

    assert response.status_code == 400


def test_empty_file_upload():

    response = client.post(
        "/api/v1/ocr/extract",
        files={
            "file": ("empty.jpg", b"", "image/jpeg")
        }
    )

    assert response.status_code == 400


def test_oversized_file_upload():

    oversized_file = b"A" * (10 * 1024 * 1024 + 1)

    response = client.post(
        "/api/v1/ocr/extract",
        files={
            "file": ("large.jpg", oversized_file, "image/jpeg")
        }
    )

    assert response.status_code == 413


def test_missing_file_upload():

    response = client.post("/api/v1/ocr/extract")

    assert response.status_code == 422


def test_invalid_image_content():

    invalid_content = b"This is not a valid image file."

    response = client.post(
        "/api/v1/ocr/extract",
        files={
            "file": ("document.png", invalid_content, "image/png")
        }
    )

    assert response.status_code == 400


# --------------------------------------------------
# MIME Type Validation Test
# --------------------------------------------------

def test_image_with_incorrect_mime_type():

    image = create_test_image("PNG")

    response = client.post(
        "/api/v1/ocr/extract",
        files={
            "file": (
                "document.jpg",
                image,
                "application/octet-stream"
            )
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert data["document"]["format"] == "PNG"
    assert data["status"] == "success"
