"""
Vison - Media Downloader
Downloads and processes media files from discovered URLs.
"""

import hashlib
import logging
import mimetypes
import os
from pathlib import Path
from urllib.parse import urlparse

import requests

from app.config import settings

logger = logging.getLogger(__name__)


def get_media_type(url: str, content_type: str = None) -> str | None:
    """Determine media type from URL extension or content-type header."""
    # Check extension
    parsed = urlparse(url)
    ext = Path(parsed.path).suffix.lower()

    if ext in settings.SUPPORTED_IMAGE_TYPES:
        return "image"
    elif ext in settings.SUPPORTED_AUDIO_TYPES:
        return "audio"
    elif ext in settings.SUPPORTED_VIDEO_TYPES:
        return "video"

    # Check content-type header
    if content_type:
        if content_type.startswith("image/"):
            return "image"
        elif content_type.startswith("audio/"):
            return "audio"
        elif content_type.startswith("video/"):
            return "video"

    return None


def generate_filename(url: str, media_type: str) -> str:
    """Generate a unique filename for a downloaded media file."""
    url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
    parsed = urlparse(url)
    ext = Path(parsed.path).suffix.lower()

    if not ext:
        ext_map = {"image": ".jpg", "audio": ".mp3", "video": ".mp4"}
        ext = ext_map.get(media_type, ".bin")

    return f"{media_type}_{url_hash}{ext}"


def download_media(url: str, media_type: str = None) -> dict | None:
    """
    Download a media file from a URL.

    Returns:
        Dict with 'file_path', 'media_type', 'file_size', 'filename' on success,
        None on failure
    """
    try:
        # Make request with streaming
        headers = {"User-Agent": settings.CRAWLER_USER_AGENT}
        response = requests.get(
            url,
            headers=headers,
            stream=True,
            timeout=settings.CRAWLER_TIMEOUT,
            allow_redirects=True,
        )
        response.raise_for_status()

        # Determine media type
        content_type = response.headers.get("Content-Type", "")
        if media_type is None:
            media_type = get_media_type(url, content_type)

        if media_type is None:
            logger.debug(f"Unsupported media type for URL: {url}")
            return None

        # Check file size
        content_length = int(response.headers.get("Content-Length", 0))
        max_size = settings.CRAWLER_MAX_FILE_SIZE_MB * 1024 * 1024
        if content_length > max_size:
            logger.warning(f"File too large ({content_length} bytes): {url}")
            return None

        # Generate filename and path
        filename = generate_filename(url, media_type)
        type_dir = settings.MEDIA_DIR / f"{media_type}s"
        type_dir.mkdir(parents=True, exist_ok=True)
        file_path = type_dir / filename

        # Download the file
        total_size = 0
        with open(file_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    total_size += len(chunk)
                    if total_size > max_size:
                        f.close()
                        file_path.unlink(missing_ok=True)
                        logger.warning(f"Download exceeded max size: {url}")
                        return None

        logger.debug(f"Downloaded {media_type}: {filename} ({total_size} bytes)")

        return {
            "file_path": str(file_path),
            "media_type": media_type,
            "file_size": total_size,
            "filename": filename,
            "url": url,
        }

    except requests.RequestException as e:
        logger.debug(f"Download failed for {url}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error downloading {url}: {e}")
        return None
