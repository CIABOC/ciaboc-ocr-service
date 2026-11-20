"""
Document type classifier.

Classifies identity documents into:
  - NIC (Sri Lankan National Identity Card)
  - PASSPORT
  - DRIVING_LICENCE
  - UNKNOWN

Classification is based on text pattern evidence, NOT on document
authenticity or identity verification. A receptionist must always
review and can correct the suggested document type.
"""

import re
from typing import Any

from app.schemas.document_schema import DocumentClassification, DocumentType


# ---------------------------------------------------------------------------
# Evidence patterns
# ---------------------------------------------------------------------------

NIC_EVIDENCE = [
    (re.compile(r"\b\d{9}[VvXx]\b"), "Old-format NIC number pattern"),
    (re.compile(r"\b\d{12}\b"), "12-digit number (possible new NIC)"),
    (
        re.compile(r"national\s*identity\s*card", re.IGNORECASE),
        "NIC label text",
    ),
    (re.compile(r"\bN\.?I\.?C\.?\b", re.IGNORECASE), "NIC abbreviation"),
    (
        re.compile(
            r"(?:ජාතික\s*හැඳුනුම්\s*පත|தேசிய\s*அடையாள\s*அட்டை)",
            re.IGNORECASE,
        ),
        "NIC label in Sinhala/Tamil",
    ),
]

PASSPORT_EVIDENCE = [
    (re.compile(r"\bpassport\b", re.IGNORECASE), "Passport label text"),
    (
        re.compile(r"^P[A-Z<][A-Z<]{3}", re.MULTILINE),
        "MRZ line 1 starting with P",
    ),
    (
        re.compile(r"[A-Z0-9<]{44}"),
        "44-character MRZ-like line",
    ),
    (
        re.compile(r"(?:date\s*of\s*expiry|nationality)", re.IGNORECASE),
        "Passport-related field labels",
    ),
    (
        re.compile(r"(?:machine\s*readable|MRZ)", re.IGNORECASE),
        "MRZ reference",
    ),
]

DRIVING_LICENCE_EVIDENCE = [
    (
        re.compile(r"driv(?:ing|er'?s?)\s*licen[cs]e", re.IGNORECASE),
        "Driving licence label",
    ),
    (
        re.compile(r"\b(?:DL|D\.L\.)\b", re.IGNORECASE),
        "DL abbreviation",
    ),
    (
        re.compile(
            r"(?:vehicle\s*class|categor(?:y|ies))",
            re.IGNORECASE,
        ),
        "Vehicle category label",
    ),
    (
        re.compile(
            r"(?:රියදුරු\s*බලපත්‍ර|ஓட்டுநர்\s*உரிமம்)",
            re.IGNORECASE,
        ),
        "Driving licence label in Sinhala/Tamil",
    ),
    (
        re.compile(r"motor\s*traffic", re.IGNORECASE),
        "Motor traffic reference",
    ),
]


class DocumentClassifier:
    """
    Classify document type based on OCR text evidence.

    Does NOT verify document authenticity.
    """

    def classify(
        self,
        ocr_lines: list[dict[str, Any]],
    ) -> DocumentClassification:
        """
        Classify the document type based on OCR line content.

        Returns a classification with evidence and confidence.
        """
        full_text = " ".join(
            line.get("text", "") for line in ocr_lines
        )

        nic_score, nic_evidence = self._score(full_text, NIC_EVIDENCE)
        passport_score, passport_evidence = self._score(
            full_text, PASSPORT_EVIDENCE
        )
        dl_score, dl_evidence = self._score(
            full_text, DRIVING_LICENCE_EVIDENCE
        )

        scores: dict[DocumentType, float] = {
            "NIC": nic_score,
            "PASSPORT": passport_score,
            "DRIVING_LICENCE": dl_score,
        }

        evidence_map: dict[DocumentType, list[str]] = {
            "NIC": nic_evidence,
            "PASSPORT": passport_evidence,
            "DRIVING_LICENCE": dl_evidence,
        }

        best_type: DocumentType = max(scores, key=scores.get)  # type: ignore[arg-type]
        best_score = scores[best_type]

        if best_score == 0:
            return DocumentClassification(
                document_type="UNKNOWN",
                confidence=0.0,
                evidence=["No document-type evidence found in OCR text."],
            )

        # Normalize confidence (more evidence → higher confidence)
        total = sum(scores.values())
        confidence = round(best_score / total, 2) if total > 0 else 0.0

        # Require meaningful separation from alternatives
        sorted_scores = sorted(scores.values(), reverse=True)
        if len(sorted_scores) >= 2 and sorted_scores[0] == sorted_scores[1]:
            # Ambiguous — report as classified but with low confidence
            confidence = min(confidence, 0.5)

        return DocumentClassification(
            document_type=best_type,
            confidence=confidence,
            evidence=evidence_map[best_type],
        )

    @staticmethod
    def _score(
        text: str,
        evidence_patterns: list[tuple[re.Pattern, str]],
    ) -> tuple[float, list[str]]:
        """Score text against evidence patterns."""
        score = 0.0
        evidence: list[str] = []

        for pattern, description in evidence_patterns:
            if pattern.search(text):
                score += 1.0
                evidence.append(description)

        return score, evidence
