
import sys
from pathlib import Path

# Add the project root to Python's import path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.services.engines.paddle_engine import PaddleOCREngine


IMAGE_PATH = PROJECT_ROOT / "samples" / "test_visitor.png"


def main():

    print("Initializing OCR engine...")

    engine = PaddleOCREngine(language="en")
    engine.initialize()

    print("Processing test image...")

    result = engine.extract_text(str(IMAGE_PATH))

    print("\n========== OCR RESULTS ==========")

    for item in result["lines"]:
        print(
            f"Text: {item['text']} | "
            f"Confidence: {item['confidence']:.4f}"
        )

    print("\n========== END ==========")


if __name__ == "__main__":
    main()
