# Deployment Guide

## Docker Build & Run

### Build

```bash
docker build -t ciaboc-ocr-service .
```

Build time: ~5–10 minutes (downloads PaddleOCR models during build).

### Run

```bash
docker run -d \
  --name ciaboc-ocr \
  -p 8000:8000 \
  -e CIABOC_OCR_APP_ENV=production \
  -e CIABOC_OCR_API_KEY=your-secret-key \
  -e CIABOC_OCR_LOG_LEVEL=WARNING \
  --memory=2g \
  --cpus=2 \
  ciaboc-ocr-service
```

### Docker Compose

```bash
# Create .env file from template
cp .env.example .env
# Edit .env with production values

# Start
docker compose up -d

# Check health
curl http://localhost:8000/health

# View logs
docker compose logs -f

# Stop
docker compose down
```

## Resource Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| CPU | 1 core | 2 cores |
| RAM | 1 GB | 2 GB |
| Disk | 2 GB (image + models) | 3 GB |

PaddleOCR model loading uses ~500 MB RAM. Each inference uses additional memory proportional to image size.

## Environment Variables

See [`.env.example`](../.env.example) for the complete list. Critical production settings:

```env
CIABOC_OCR_APP_ENV=production
CIABOC_OCR_API_KEY=<strong-random-key>
CIABOC_OCR_LOG_LEVEL=WARNING
CIABOC_OCR_OCR_MAX_CONCURRENCY=2
CIABOC_OCR_RATE_LIMIT_REQUESTS=60
```

## Model Initialization

PaddleOCR models are downloaded during the Docker build (cached in the image). The container does **not** download models at startup.

If models need updating, rebuild the Docker image.

## Health Checks

The Dockerfile includes a built-in health check:

```
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3
```

The 60-second start period allows time for PaddleOCR model loading on first request.

## Production Checklist

- [ ] Set `CIABOC_OCR_APP_ENV=production`
- [ ] Set a strong `CIABOC_OCR_API_KEY`
- [ ] Set `CIABOC_OCR_LOG_LEVEL=WARNING`
- [ ] Run behind HTTPS reverse proxy (nginx/Traefik)
- [ ] Restrict network — only Spring Boot backend can reach port 8000
- [ ] Set Docker memory limit (2 GB recommended)
- [ ] Set Docker CPU limit (2 cores recommended)
- [ ] Verify health endpoint: `GET /health`
- [ ] Verify Swagger UI is disabled (should return 404 on `/docs`)
- [ ] Run `pip audit` on dependencies
- [ ] Review `.env` — ensure no default/empty API key
