
from paddleocr import PaddleOCR

from app.services.engines.base_engine import BaseOCREngine


class PaddleOCREngine(BaseOCREngine):

    def __init__(self, language: str = "en"):
        self.language = language
        self.engine = None

    def initialize(self) -> None:
        self.engine = PaddleOCR(
            lang=self.language,
            device="cpu",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )

    def extract_text(self, image) -> dict:

        if self.engine is None:
            raise RuntimeError("OCR engine has not been initialized.")

        results = self.engine.predict(image)

        extracted_lines = []

        for result in results:
            result_data = result.json

            if "res" in result_data:
                result_data = result_data["res"]

            texts = result_data.get("rec_texts", [])
            scores = result_data.get("rec_scores", [])

            for text, score in zip(texts, scores):
                extracted_lines.append({
                    "text": text,
                    "confidence": float(score)
                })

        return {
            "language": self.language,
            "lines": extracted_lines
        }
