# ============================================================
# CIABOC OCR Service — Dockerfile
# ============================================================
# CPU-only PaddleOCR deployment.
# Runs as non-root user for security.
# Models are downloaded during the build stage.
# ============================================================

FROM python:3.13-slim AS base

# System dependencies for PaddlePaddle and image processing
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
        libsm6 \
        libxrender1 \
        libxext6 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd --gid 1000 ocruser && \
    useradd --uid 1000 --gid 1000 --create-home ocruser

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download PaddleOCR models during build (cached in image)
RUN python -c "\
from paddleocr import PaddleOCR; \
ocr = PaddleOCR(lang='en', device='cpu', \
    use_doc_orientation_classify=False, \
    use_doc_unwarping=False, \
    use_textline_orientation=False); \
print('Models downloaded.')"

# Copy application code
COPY app/ ./app/

# Switch to non-root user
USER ocruser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Run with uvicorn
CMD ["python", "-m", "uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--limit-concurrency", "10", \
     "--limit-max-requests", "10000", \
     "--timeout-keep-alive", "30"]
