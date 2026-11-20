# Security Documentation

## Overview

The CIABOC OCR Service processes sensitive identity information (NIC numbers, passport numbers, names, dates of birth). Security is a mandatory requirement throughout.

---

## Upload Security

| Control | Implementation |
|---------|---------------|
| File size limit | 10 MB enforced during chunked upload |
| Pixel limit | 25 megapixels maximum |
| Format validation | Actual image content validated via Pillow (not MIME type or extension) |
| Corrupted images | Rejected via `image.verify()` |
| Decompression bombs | Pillow `DecompressionBombWarning` treated as error |
| Multi-frame/animated | Rejected if `n_frames > 1` |
| Unsupported formats | Only JPEG and PNG accepted |
| In-memory processing | Images processed in memory, never saved to disk |

## API Security

| Control | Implementation |
|---------|---------------|
| Authentication | API key via `X-API-Key` header (constant-time comparison) |
| Rate limiting | Sliding-window per client IP (60 req / 60s default) |
| Concurrency limiting | Bounded semaphore (2 concurrent OCR operations default) |
| Error sanitization | No stack traces or internal details in error responses |
| Exempt paths | `/health`, `/docs`, `/openapi.json` bypass auth |
| Swagger UI | Disabled in production (`APP_ENV=production`) |

## Privacy Controls

| Principle | Implementation |
|-----------|---------------|
| **No permanent image storage** | Images processed in-memory, `bytearray.clear()` after processing |
| **No PII logging** | Logger never receives NIC numbers, names, DOB, addresses, MRZ text, or raw OCR output |
| **No external API calls** | PaddleOCR runs locally, no cloud OCR services |
| **No database access** | OCR service never connects to PostgreSQL |
| **Temporary data cleanup** | `finally` blocks ensure cleanup even on errors |
| **Git-safe samples** | `.gitignore` excludes real document images from repository |

## Deployment Security

| Control | Implementation |
|---------|---------------|
| Non-root container | Docker `USER ocruser` (UID 1000) |
| Secrets management | Environment variables, never hardcoded |
| Resource limits | Docker Compose: 2 CPU, 2GB RAM limits |
| Health checks | Built into Dockerfile and docker-compose.yml |
| Dependency pinning | All versions pinned in `requirements.txt` |

## Configuration

Generate a production API key:

```python
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Set via environment variable:
```
CIABOC_OCR_API_KEY=your-generated-key
```

## CORS Policy

CORS is **not** enabled by default. The React frontend should call the Spring Boot backend, not the OCR service directly. If CORS is required, configure `CIABOC_OCR_CORS_ORIGINS`.

## Recommendations Before Deployment

1. Set a strong `CIABOC_OCR_API_KEY`
2. Set `CIABOC_OCR_APP_ENV=production` (disables Swagger UI)
3. Run behind a reverse proxy (nginx/Traefik) with HTTPS
4. Review `requirements.txt` for known vulnerabilities (`pip audit`)
5. Restrict network access — only the Spring Boot backend should reach port 8000
6. Set `CIABOC_OCR_LOG_LEVEL=WARNING` in production
