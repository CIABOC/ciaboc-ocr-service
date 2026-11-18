
from io import BytesIO
import warnings

from PIL import Image, UnidentifiedImageError


MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_IMAGE_PIXELS = 25_000_000      # 25 megapixels

ALLOWED_FORMATS = {"JPEG", "PNG"}


class ImageValidationError(Exception):
    """Raised when an uploaded image fails validation."""


def validate_image(image_bytes: bytes) -> dict:
    """
    Validate image content, format and dimensions.

    The function does not save the uploaded image.
    """

    if not image_bytes:
        raise ImageValidationError("The uploaded image is empty.")

    if len(image_bytes) > MAX_IMAGE_SIZE:
        raise ImageValidationError("The uploaded image exceeds the size limit.")

    try:
        # Treat Pillow decompression warnings as errors.
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)

            with Image.open(BytesIO(image_bytes)) as image:

                if image.format not in ALLOWED_FORMATS:
                    raise ImageValidationError(
                        "Unsupported image format. Use JPEG or PNG."
                    )

                width, height = image.size

                if width <= 0 or height <= 0:
                    raise ImageValidationError("Invalid image dimensions.")

                if width * height > MAX_IMAGE_PIXELS:
                    raise ImageValidationError(
                        "Image dimensions exceed the allowed limit."
                    )

                image.verify()

        return {
            "format": image.format,
            "width": width,
            "height": height
        }

    except ImageValidationError:
        raise

    except (
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise ImageValidationError(
            "The uploaded file is not a valid supported image."
        ) from exc
