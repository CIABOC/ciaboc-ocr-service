# OCR Evaluation Report

## Summary

| Aspect | Status |
|--------|--------|
| English OCR | ✅ Supported (PaddleOCR 3.7.0 English model) |
| Sinhala OCR | ⚠ Not currently supported — requires separate model |
| Tamil OCR | ⚠ Not currently supported — requires separate model |
| Real document evaluation | ❌ Not performed — requires authorized anonymized samples |

## PaddleOCR 3.7.0 — Installed Model

The current installation uses PaddleOCR 3.7.0 with:
- **Detection model:** English text detection
- **Recognition model:** English text recognition
- **Device:** CPU only
- **Language:** `en` (English)

## English Evaluation (Synthetic)

### Test: Clean Synthetic English Image

A synthetic test image with clear black text on white background was processed.

**Result:**
- Lines extracted: 7
- Average confidence: ~99.6%
- All expected text correctly recognized

### Limitations of This Test

> **⚠ Important:** This result only demonstrates that PaddleOCR can read clean, computer-generated English text. It does NOT indicate:
> - Real identity document accuracy
> - Handwritten text capability
> - Performance on blurry, rotated, or low-quality images
> - Sinhala or Tamil text capability

## Sinhala Language Support

PaddleOCR does not include Sinhala as a built-in language. Options:

1. **Custom trained model** — Train a PaddleOCR model on Sinhala text data
2. **Google Cloud Vision API** — Supports Sinhala (but violates the no-external-API requirement)
3. **Tesseract OCR** — Has community Sinhala models (`sin` language pack), could be added as a secondary engine

**Recommendation:** Investigate Tesseract as a secondary engine for Sinhala, keeping PaddleOCR for English. The engine interface is modular (`BaseOCREngine`) to support this.

## Tamil Language Support

PaddleOCR has a Tamil model (`ta` language). It can be enabled by:

1. Creating a second `PaddleOCREngine` instance with `language="ta"`
2. Selecting the engine based on detected script or user hint

**Recommendation:** Test the PaddleOCR Tamil model with synthetic Tamil text before deploying.

## Accuracy Metrics (Definitions)

| Metric | Definition |
|--------|-----------|
| **CER** (Character Error Rate) | Edit distance between predicted and ground truth characters / total characters |
| **WER** (Word Error Rate) | Edit distance between predicted and ground truth words / total words |
| **Field-level exact match** | Percentage of fields where extracted value exactly matches ground truth |
| **Classification accuracy** | Percentage of documents correctly classified by type |
| **Processing time** | End-to-end time from image upload to response |

## Evaluation Gaps

The following evaluations require authorized, anonymized document samples:

- [ ] Real Sri Lankan NIC (old format) — English + Sinhala/Tamil
- [ ] Real Sri Lankan NIC (new format)
- [ ] Real passport with MRZ
- [ ] Real driving licence
- [ ] Blurry / low-resolution images
- [ ] Rotated images
- [ ] Images with poor lighting
- [ ] Partial / cropped documents

## Recommendations

1. **Do not claim language support** for Sinhala or Tamil until models are tested
2. **Do not claim accuracy** beyond what synthetic English tests demonstrate
3. **Obtain authorized anonymized samples** for real evaluation
4. **Test Tamil PaddleOCR model** (`lang="ta"`) with synthetic Tamil text
5. **Investigate Tesseract** as a secondary engine for Sinhala
6. **Measure CER/WER** on real documents when samples are available
7. **Document confidence calibration** — OCR confidence ≠ actual accuracy
