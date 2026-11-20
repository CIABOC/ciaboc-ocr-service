import os
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    # Application
    app_env: str = "development"
    app_title: str = "CIABOC OCR Service"
    app_version: str = "1.0.0"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # OCR
    ocr_language: str = "en"
    ocr_device: str = "cpu"
    ocr_max_concurrency: int = 2
    ocr_timeout_seconds: int = 30

    # Upload limits
    max_upload_size_mb: int = 10
    max_image_pixels: int = 25_000_000

    # Security
    api_key: str = ""
    api_key_header: str = "X-API-Key"
    cors_origins: str = ""
    rate_limit_requests: int = 60
    rate_limit_window_seconds: int = 60

    # Logging
    log_level: str = "INFO"

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def is_development(self) -> bool:
        return self.app_env.lower() == "development"

    @property
    def cors_origin_list(self) -> list[str]:
        if not self.cors_origins:
            return []
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    model_config = {
        "env_prefix": "CIABOC_OCR_",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


@lru_cache()
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
