
from abc import ABC, abstractmethod
from typing import Any


class BaseOCREngine(ABC):

    @abstractmethod
    def initialize(self) -> None:
        """Initialize the OCR engine."""
        pass

    @abstractmethod
    def extract_text(self, image: Any) -> dict:
        """Extract text and confidence information from an image."""
        pass

