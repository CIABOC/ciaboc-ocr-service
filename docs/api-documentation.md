# API Documentation

## Base URL

```
http://localhost:8000
```

## Authentication

All `/api/v1/*` endpoints require an `X-API-Key` header in production. In development (when `CIABOC_OCR_API_KEY` is empty), authentication is disabled.

```
X-API-Key: your-secret-api-key
```

---

## Endpoints

### GET /health

Health check. No authentication required.

**Response 200:**
```json
{
  "status": "healthy",
  "service": "CIABOC OCR Service"
}
```

---

### GET /api/v1/ocr/status

OCR engine availability check.

**Response 200:**
```json
{
  "status": "available",
  "message": "OCR service is ready"
}
```

---

### POST /api/v1/ocr/extract

Upload an identity document image for text extraction and structured field extraction.

**Request:**
- Content-Type: `multipart/form-data`
- Body: `file` — JPEG or PNG image (max 10 MB, max 25 megapixels)
- Query parameter (optional): `document_type` — `NIC`, `PASSPORT`, or `DRIVING_LICENCE`

**Response 200:**
```json
{
  "status": "success",
  "message": "Document text extracted successfully.",
  "document": {
    "format": "JPEG",
    "width": 1200,
    "height": 800
  },
  "ocr_result": {
    "language": "en",
    "lines": [
      {
        "text": "NATIONAL IDENTITY CARD",
        "confidence": 0.9912
      },
      {
        "text": "NIC No: 912345678V",
        "confidence": 0.9856
      },
      {
        "text": "Name: KAMAL PERERA",
        "confidence": 0.9741
      }
    ]
  },
  "extraction": {
    "classification": {
      "document_type": "NIC",
      "confidence": 0.75,
      "evidence": [
        "NIC label text",
        "Old-format NIC number pattern"
      ]
    },
    "nic": {
      "nic_number": {
        "value": "912345678V",
        "raw_text": "NIC No: 912345678V",
        "confidence": 0.9856,
        "needs_verification": true
      },
      "full_name": {
        "value": "KAMAL PERERA",
        "raw_text": "Name: KAMAL PERERA",
        "confidence": 0.9741,
        "needs_verification": true
      },
      "date_of_birth": {
        "value": "1991-05-15",
        "raw_text": "NIC No: 912345678V",
        "confidence": 0.9856,
        "needs_verification": true
      },
      "gender": {
        "value": "Male",
        "raw_text": "NIC No: 912345678V",
        "confidence": 0.9856,
        "needs_verification": true
      },
      "address": {
        "value": null,
        "raw_text": null,
        "confidence": null,
        "needs_verification": true
      },
      "nic_format": "old"
    },
    "passport": null,
    "driving_licence": null,
    "raw_text": [
      "NATIONAL IDENTITY CARD",
      "NIC No: 912345678V",
      "Name: KAMAL PERERA"
    ],
    "extraction_notes": []
  },
  "processing_time_ms": 234.5,
  "verification_required": true
}
```

---

## Error Responses

| Status | Meaning | Example |
|--------|---------|---------|
| 400 | Invalid image | `{"detail": "Unsupported image format. Use JPEG or PNG."}` |
| 401 | No API key provided | `{"detail": "Authentication required."}` |
| 403 | Invalid API key | `{"detail": "Invalid authentication credentials."}` |
| 413 | File too large | `{"detail": "Uploaded file exceeds the 10 MB limit."}` |
| 422 | Missing file parameter | Validation error |
| 429 | Rate limit exceeded | `{"detail": "Too many requests. Please try again later."}` |
| 500 | Internal error | `{"detail": "Document processing failed."}` |
| 503 | OCR busy | `{"detail": "OCR service is busy. Please try again shortly."}` |

## Rate Limiting

Default: 60 requests per 60-second sliding window per client IP. Configurable via `CIABOC_OCR_RATE_LIMIT_REQUESTS` and `CIABOC_OCR_RATE_LIMIT_WINDOW_SECONDS`.

## Concurrency

Maximum 2 concurrent OCR operations (configurable via `CIABOC_OCR_OCR_MAX_CONCURRENCY`). Additional requests receive HTTP 503.
