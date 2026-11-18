
from io import BytesIO
from threading import Lock

import numpy as np
from PIL import Image, ImageOps

from app.services.engines.paddle_engine import PaddleOCREngine


class OCRService:

    def __init__(self):
        self.engine = PaddleOCREngine(language="en")
        self.initialized = False
        self.lock = Lock()

    def initialize(self):

        with self.lock:
            if not self.initialized:
                self.engine.initialize()
                self.initialized = True

    def extract(self, image_bytes: bytes) -> dict:

        self.initialize()

        with Image.open(BytesIO(image_bytes)) as image:
            image = ImageOps.exif_transpose(image)
            image = image.convert("RGB")
            image_array = np.asarray(image).copy()

        return self.engine.extract_text(image_array)


ocr_service = OCRService()
