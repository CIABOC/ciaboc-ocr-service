
from fastapi import APIRouter, UploadFile, File, HTTPException
from starlette.concurrency import run_in_threadpool

from app.utils.image_processor import (
    validate_image,
    ImageValidationError,
    MAX_IMAGE_SIZE
)
from app.services.ocr_service import ocr_service
from app.schemas.ocr_schema import OCRResponse


router = APIRouter()

CHUNK_SIZE = 1024 * 1024


@router.get("/status")
async def ocr_status():
    return {
        "status": "available",
        "message": "OCR service is ready"
    }


@router.post("/extract", response_model=OCRResponse)
async def extract_document(file: UploadFile = File(...)):

    image_bytes = bytearray()

    try:
        while True:
            remaining = MAX_IMAGE_SIZE + 1 - len(image_bytes)

            chunk = await file.read(
                min(CHUNK_SIZE, remaining)
            )

            if not chunk:
                break

            image_bytes.extend(chunk)

            if len(image_bytes) > MAX_IMAGE_SIZE:
                raise HTTPException(
                    status_code=413,
                    detail="Uploaded file exceeds the 10 MB limit."
                )

        image_info = validate_image(bytes(image_bytes))

        result = await run_in_threadpool(
            ocr_service.extract,
            bytes(image_bytes)
        )

        return {
            "status": "success",
            "message": "Document text extracted successfully.",
            "document": {
                "format": image_info["format"],
                "width": image_info["width"],
                "height": image_info["height"]
            },
            "ocr_result": result,
            "verification_required": True
        }

    except ImageValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        )

    except HTTPException:
        raise

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Document processing failed."
        )

    finally:
        image_bytes.clear()
        await file.close()
