"""
Vison - Configuration Module
Central configuration for the multimedia search engine.
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with environment variable overrides."""

    # Application
    APP_NAME: str = "Vison"
    APP_VERSION: str = "1.0.0"
    APP_DESCRIPTION: str = "Reverse Multimedia Search Engine"
    DEBUG: bool = True

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    MEDIA_DIR: Path = DATA_DIR / "media"
    THUMBNAILS_DIR: Path = DATA_DIR / "thumbnails"
    INDEX_DIR: Path = DATA_DIR / "indices"
    DB_PATH: Path = DATA_DIR / "vison.db"
    UPLOAD_DIR: Path = DATA_DIR / "uploads"

    # Feature Extraction
    IMAGE_FEATURE_DIM: int = 1280  # MobileNetV2 output dimension
    AUDIO_FEATURE_DIM: int = 512   # MFCC-based feature dimension
    VIDEO_FEATURE_DIM: int = 1280  # Averaged frame features
    TEXT_FEATURE_DIM: int = 5000   # TF-IDF max features

    # Search
    DEFAULT_TOP_K: int = 20
    MAX_TOP_K: int = 100
    SIMILARITY_THRESHOLD: float = 0.1

    # Crawler
    CRAWLER_MAX_DEPTH: int = 3
    CRAWLER_MAX_PAGES: int = 100
    CRAWLER_DELAY_SECONDS: float = 1.0
    CRAWLER_TIMEOUT: int = 30
    CRAWLER_USER_AGENT: str = "Vison-Crawler/1.0 (Research Multimedia Search Engine)"
    CRAWLER_MAX_FILE_SIZE_MB: int = 50

    # Supported file types
    SUPPORTED_IMAGE_TYPES: list[str] = [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff"]
    SUPPORTED_AUDIO_TYPES: list[str] = [".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac"]
    SUPPORTED_VIDEO_TYPES: list[str] = [".mp4", ".avi", ".mkv", ".mov", ".webm", ".flv"]

    # Image processing
    IMAGE_INPUT_SIZE: tuple[int, int] = (224, 224)
    THUMBNAIL_SIZE: tuple[int, int] = (300, 300)

    # OpenVINO
    USE_OPENVINO: bool = True  # Falls back to TensorFlow if unavailable

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()


def ensure_directories():
    """Create all required directories if they don't exist."""
    for dir_path in [
        settings.DATA_DIR,
        settings.MEDIA_DIR,
        settings.THUMBNAILS_DIR,
        settings.INDEX_DIR,
        settings.UPLOAD_DIR,
        settings.MEDIA_DIR / "images",
        settings.MEDIA_DIR / "audio",
        settings.MEDIA_DIR / "video",
    ]:
        dir_path.mkdir(parents=True, exist_ok=True)
