"""
Document extraction service.

Orchestrates:
  1. Document-type classification
  2. Type-specific field extraction
  3. Result assembly

This service sits between the OCR engine (which produces raw text)
and the API layer (which returns structured responses).
"""

from typing import Any

from app.services.document_classifier import DocumentClassifier
from app.services.extractors.nic_extractor import NICExtractor
from app.services.extractors.passport_extractor import PassportExtractor
from app.services.extractors.driving_licence_extractor import (
    DrivingLicenceExtractor,
)
from app.schemas.document_schema import (
    DocumentExtractionResult,
    DocumentClassification,
)


class DocumentExtractionService:
    """
    Coordinates document classification and field extraction.

    Usage:
        service = DocumentExtractionService()
        result = service.extract(ocr_lines)
    """

    def __init__(self) -> None:
        self.classifier = DocumentClassifier()
        self.extractors = {
            "NIC": NICExtractor(),
            "PASSPORT": PassportExtractor(),
            "DRIVING_LICENCE": DrivingLicenceExtractor(),
        }

    def extract(
        self,
        ocr_lines: list[dict[str, Any]],
        document_type_hint: str | None = None,
    ) -> DocumentExtractionResult:
        """
        Classify the document and extract structured fields.

        Args:
            ocr_lines: List of dicts with 'text' and 'confidence' keys.
            document_type_hint: Optional hint to override auto-classification.
                A receptionist may provide this when correcting the
                suggested document type.

        Returns:
            DocumentExtractionResult with classification and extracted fields.
        """
        raw_texts = [line.get("text", "") for line in ocr_lines]

        # Classify document type
        if document_type_hint and document_type_hint in self.extractors:
            classification = DocumentClassification(
                document_type=document_type_hint,  # type: ignore[arg-type]
                confidence=None,
                evidence=["Document type provided by user hint."],
            )
        else:
            classification = self.classifier.classify(ocr_lines)

        # Run the appropriate extractor
        doc_type = classification.document_type
        extractor = self.extractors.get(doc_type)

        if extractor is None:
            # Unknown document type — return raw text only
            return DocumentExtractionResult(
                classification=classification,
                raw_text=raw_texts,
                extraction_notes=[
                    "Document type could not be determined. "
                    "Only raw OCR text is available."
                ],
            )

        # Run extraction
        result = extractor.extract(ocr_lines)

        # Override classification with the classifier's result
        # (the extractor sets its own, but the classifier's is authoritative)
        result.classification = classification

        return result


# Module-level singleton
document_extraction_service = DocumentExtractionService()
