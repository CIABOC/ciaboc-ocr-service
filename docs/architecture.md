# Architecture

## System Overview

The CIABOC OCR Service is a standalone microservice that processes identity document images and returns structured text extraction results. It is called exclusively by the Spring Boot backend.

```
┌─────────────────────────────────────────────────────────┐
│                    React Frontend                       │
│  (Receptionist uploads document image)                  │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP
┌──────────────────────▼──────────────────────────────────┐
│               Spring Boot Backend                       │
│  - Authorization & session management                   │
│  - Calls OCR Service with X-API-Key                     │
│  - Presents results to receptionist                     │
│  - Receptionist reviews & corrects                      │
│  - Saves verified data to PostgreSQL                    │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP (authenticated)
┌──────────────────────▼──────────────────────────────────┐
│            FastAPI OCR Service (this service)            │
│                                                         │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ API Layer   │→ │ OCR Service  │→ │ PaddleOCR     │  │
│  │ (routes)    │  │              │  │ Engine        │  │
│  └─────────────┘  └──────┬───────┘  └───────────────┘  │
│                          │                              │
│                   ┌──────▼───────┐                      │
│                   │  Document    │                      │
│                   │  Classifier  │                      │
│                   └──────┬───────┘                      │
│                          │                              │
│            ┌─────────────┼─────────────┐                │
│            ▼             ▼             ▼                │
│     ┌────────────┐ ┌──────────┐ ┌──────────┐           │
│     │ NIC        │ │ Passport │ │ Driving  │           │
│     │ Extractor  │ │ Extractor│ │ Licence  │           │
│     └────────────┘ └──────────┘ │ Extractor│           │
│                                 └──────────┘           │
└─────────────────────────────────────────────────────────┘
```

## Component Descriptions

### API Layer (`app/api/routes/ocr.py`)
- Receives image uploads via multipart/form-data
- Validates image format, size, and dimensions
- Manages OCR concurrency
- Returns structured JSON responses

### OCR Service (`app/services/ocr_service.py`)
- Thread-safe PaddleOCR initialization
- EXIF orientation correction
- Converts images to NumPy arrays for PaddleOCR

### PaddleOCR Engine (`app/services/engines/paddle_engine.py`)
- Wraps PaddleOCR 3.7.0
- CPU-only inference
- Returns raw text lines with confidence scores

### Document Classifier (`app/services/document_classifier.py`)
- Pattern-based document type detection
- Returns classification with evidence and confidence
- Supports: NIC, PASSPORT, DRIVING_LICENCE, UNKNOWN

### Document Extractors (`app/services/extractors/`)
- **NIC Extractor**: Old/new format NIC numbers, DOB/gender derivation, label matching
- **Passport Extractor**: TD3 MRZ parsing with ICAO 9303 check digits, label fallback
- **Driving Licence Extractor**: Label-based field extraction

### Security Layer (`app/core/security.py`)
- API key authentication middleware
- Rate limiting middleware
- OCR concurrency limiter
- Error sanitization middleware

## Data Flow

1. Spring Boot sends image → API endpoint
2. Image validated (format, size, pixels, integrity)
3. Concurrency slot acquired
4. PaddleOCR extracts raw text lines
5. Document classifier identifies document type
6. Appropriate extractor extracts structured fields
7. JSON response returned with raw text + extraction + classification
8. Spring Boot presents to receptionist for verification
