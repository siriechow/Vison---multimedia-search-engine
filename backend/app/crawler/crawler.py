"""
Vison - Web Crawler
Selenium-based web crawler for discovering and indexing multimedia content.
"""

import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse
from typing import Optional

from bs4 import BeautifulSoup

from app.config import settings
from app.crawler.media_downloader import download_media, get_media_type
from app.ml.feature_extractor import (
    extract_image_features,
    extract_audio_features,
    extract_video_features,
    generate_thumbnail,
)
from app.ml.text_analyzer import extract_keywords
from app.search.database import database
from app.search.vector_store import vector_store

logger = logging.getLogger(__name__)


class WebCrawler:
    """
    Selenium-based web crawler that discovers and indexes multimedia content.
    Runs in a background thread to avoid blocking the API.
    """

    def __init__(self):
        self._driver = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._current_session_id: Optional[int] = None
        self._status = "idle"
        self._pages_crawled = 0
        self._items_found = 0

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def status(self) -> dict:
        return {
            "status": self._status,
            "session_id": self._current_session_id,
            "pages_crawled": self._pages_crawled,
            "items_found": self._items_found,
            "is_running": self.is_running,
        }

    def _create_driver(self):
        """Create a headless Selenium WebDriver."""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service

            options = Options()
            options.add_argument("--headless=new")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument(f"--user-agent={settings.CRAWLER_USER_AGENT}")
            options.add_argument("--window-size=1920,1080")
            options.add_argument("--disable-extensions")
            options.add_argument("--disable-images")

            try:
                from webdriver_manager.chrome import ChromeDriverManager
                service = Service(ChromeDriverManager().install())
                driver = webdriver.Chrome(service=service, options=options)
            except Exception:
                driver = webdriver.Chrome(options=options)

            driver.set_page_load_timeout(settings.CRAWLER_TIMEOUT)
            return driver

        except Exception as e:
            logger.error(f"Failed to create WebDriver: {e}")
            return None

    def _extract_media_urls(self, page_source: str, base_url: str) -> list[dict]:
        """Extract media URLs from HTML page source."""
        soup = BeautifulSoup(page_source, "html.parser")
        media_urls = []

        # Extract images
        for tag in soup.find_all("img"):
            src = tag.get("src") or tag.get("data-src")
            if src:
                url = urljoin(base_url, src)
                alt = tag.get("alt", "")
                media_urls.append({
                    "url": url,
                    "media_type": "image",
                    "title": alt,
                    "source_url": base_url,
                })

        # Extract audio
        for tag in soup.find_all(["audio", "source"]):
            src = tag.get("src")
            if src and get_media_type(src) == "audio":
                url = urljoin(base_url, src)
                media_urls.append({
                    "url": url,
                    "media_type": "audio",
                    "title": "",
                    "source_url": base_url,
                })

        # Extract video
        for tag in soup.find_all(["video", "source"]):
            src = tag.get("src")
            if src and get_media_type(src) == "video":
                url = urljoin(base_url, src)
                media_urls.append({
                    "url": url,
                    "media_type": "video",
                    "title": "",
                    "source_url": base_url,
                })

        # Extract links to media files
        for tag in soup.find_all("a", href=True):
            href = tag.get("href", "")
            url = urljoin(base_url, href)
            mt = get_media_type(url)
            if mt:
                media_urls.append({
                    "url": url,
                    "media_type": mt,
                    "title": tag.get_text(strip=True)[:200],
                    "source_url": base_url,
                })

        return media_urls

    def _extract_page_links(self, page_source: str, base_url: str) -> list[str]:
        """Extract discoverable page links from HTML."""
        soup = BeautifulSoup(page_source, "html.parser")
        links = set()
        base_domain = urlparse(base_url).netloc

        for tag in soup.find_all("a", href=True):
            href = tag.get("href", "")
            url = urljoin(base_url, href)
            parsed = urlparse(url)

            # Only follow links on the same domain
            if parsed.netloc == base_domain and parsed.scheme in ("http", "https"):
                # Clean URL (remove fragments)
                clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                if parsed.query:
                    clean_url += f"?{parsed.query}"
                links.add(clean_url)

        return list(links)

    def _index_media_item(self, media_info: dict) -> bool:
        """Download, extract features, and index a media item."""
        try:
            # Download the media file
            download_result = download_media(media_info["url"], media_info["media_type"])
            if download_result is None:
                return False

            file_path = download_result["file_path"]
            media_type = download_result["media_type"]

            # Extract features based on media type
            features = None
            if media_type == "image":
                features = extract_image_features(file_path)
            elif media_type == "audio":
                features = extract_audio_features(file_path)
            elif media_type == "video":
                features = extract_video_features(file_path)

            if features is None:
                logger.warning(f"Feature extraction failed for {media_info['url']}")
                return False

            # Generate thumbnail
            thumb_filename = Path(download_result["filename"]).stem + "_thumb.jpg"
            thumb_path = settings.THUMBNAILS_DIR / thumb_filename
            generate_thumbnail(file_path, thumb_path, media_type)

            # Extract keywords from title
            keywords = ", ".join(extract_keywords(media_info.get("title", ""), top_n=10))

            # Store metadata in database
            item_id = database.add_media_item(
                media_type=media_type,
                title=media_info.get("title", ""),
                description=media_info.get("description", ""),
                url=media_info["url"],
                source_url=media_info.get("source_url", ""),
                file_path=file_path,
                thumbnail_path=str(thumb_path) if thumb_path.exists() else None,
                file_size=download_result["file_size"],
                keywords=keywords,
            )

            # Add to vector store
            vector_store.add(media_type, item_id, features)

            logger.info(f"Indexed {media_type} #{item_id}: {media_info['url'][:80]}")
            return True

        except Exception as e:
            logger.error(f"Failed to index media: {e}")
            return False

    def _crawl_worker(self, start_url: str, max_depth: int, max_pages: int):
        """Background worker that performs the actual crawling."""
        self._status = "running"
        visited = set()
        queue = [(start_url, 0)]  # (url, depth)

        try:
            # Try to use Selenium, fall back to requests
            use_selenium = False
            driver = self._create_driver()
            if driver:
                use_selenium = True
                logger.info("Using Selenium for crawling")
            else:
                logger.info("Selenium unavailable, using requests for crawling")

            while queue and not self._stop_event.is_set():
                if self._pages_crawled >= max_pages:
                    logger.info(f"Reached max pages limit ({max_pages})")
                    break

                url, depth = queue.pop(0)

                if url in visited:
                    continue

                if depth > max_depth:
                    continue

                visited.add(url)
                logger.info(f"Crawling [{depth}]: {url}")

                try:
                    # Fetch page
                    if use_selenium:
                        driver.get(url)
                        time.sleep(1)  # Wait for JS rendering
                        page_source = driver.page_source
                        page_title = driver.title
                    else:
                        import requests as req
                        resp = req.get(
                            url,
                            headers={"User-Agent": settings.CRAWLER_USER_AGENT},
                            timeout=settings.CRAWLER_TIMEOUT,
                        )
                        resp.raise_for_status()
                        page_source = resp.text
                        page_title = ""
                        soup = BeautifulSoup(page_source, "html.parser")
                        title_tag = soup.find("title")
                        if title_tag:
                            page_title = title_tag.get_text(strip=True)

                    # Record crawled page
                    database.add_crawled_page(
                        session_id=self._current_session_id,
                        url=url,
                        title=page_title,
                        depth=depth,
                        status_code=200,
                        content_type="text/html",
                    )
                    self._pages_crawled += 1

                    # Extract and index media
                    media_urls = self._extract_media_urls(page_source, url)
                    for media_info in media_urls:
                        if self._stop_event.is_set():
                            break
                        if self._index_media_item(media_info):
                            self._items_found += 1

                    # Update session progress
                    database.update_crawl_session(
                        self._current_session_id,
                        pages_crawled=self._pages_crawled,
                        items_found=self._items_found,
                    )

                    # Extract page links for further crawling
                    if depth < max_depth:
                        page_links = self._extract_page_links(page_source, url)
                        for link in page_links:
                            if link not in visited:
                                queue.append((link, depth + 1))

                    # Politeness delay
                    time.sleep(settings.CRAWLER_DELAY_SECONDS)

                except Exception as e:
                    logger.warning(f"Error crawling {url}: {e}")
                    continue

            # Cleanup
            if driver:
                driver.quit()

            # Save vector store
            vector_store.save()

            # Update session status
            status = "stopped" if self._stop_event.is_set() else "completed"
            database.update_crawl_session(
                self._current_session_id,
                status=status,
                pages_crawled=self._pages_crawled,
                items_found=self._items_found,
            )
            self._status = status
            logger.info(
                f"Crawl {status}: {self._pages_crawled} pages, {self._items_found} items indexed"
            )

        except Exception as e:
            logger.error(f"Crawler error: {e}")
            database.update_crawl_session(
                self._current_session_id,
                status="failed",
                error_message=str(e),
            )
            self._status = "failed"

    def start(self, url: str, max_depth: int = None, max_pages: int = None) -> dict:
        """Start a crawling session in a background thread."""
        if self.is_running:
            return {"error": "Crawler is already running", "status": self.status}

        max_depth = max_depth or settings.CRAWLER_MAX_DEPTH
        max_pages = max_pages or settings.CRAWLER_MAX_PAGES

        # Create session
        self._current_session_id = database.create_crawl_session(url, max_depth)
        self._pages_crawled = 0
        self._items_found = 0
        self._stop_event.clear()

        # Start background thread
        self._thread = threading.Thread(
            target=self._crawl_worker,
            args=(url, max_depth, max_pages),
            daemon=True,
        )
        self._thread.start()

        database.update_crawl_session(self._current_session_id, status="running")

        logger.info(f"Crawl started: {url} (depth={max_depth}, max_pages={max_pages})")
        return {
            "message": "Crawl started",
            "session_id": self._current_session_id,
            "status": self.status,
        }

    def stop(self) -> dict:
        """Stop the active crawling session."""
        if not self.is_running:
            return {"message": "No active crawl to stop", "status": self.status}

        self._stop_event.set()
        self._thread.join(timeout=10)

        return {"message": "Crawl stop requested", "status": self.status}


# Singleton
crawler = WebCrawler()
