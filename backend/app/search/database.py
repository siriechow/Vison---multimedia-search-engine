"""
Vison - Database Module
SQLite-backed metadata store for indexed media items.
"""

import logging
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


class Database:
    """Thread-safe SQLite database for storing media item metadata."""

    def __init__(self):
        self._local = threading.local()
        self._initialized = False

    def _get_connection(self) -> sqlite3.Connection:
        """Get a thread-local database connection."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(str(settings.DB_PATH), check_same_thread=False)
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA foreign_keys=ON")
        return self._local.conn

    def initialize(self):
        """Create database tables if they don't exist."""
        conn = self._get_connection()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS media_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                media_type TEXT NOT NULL CHECK(media_type IN ('image', 'audio', 'video')),
                title TEXT,
                description TEXT,
                url TEXT,
                source_url TEXT,
                file_path TEXT,
                thumbnail_path TEXT,
                file_size INTEGER DEFAULT 0,
                width INTEGER,
                height INTEGER,
                duration REAL,
                keywords TEXT,
                indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS crawl_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_url TEXT NOT NULL,
                status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'running', 'completed', 'failed', 'stopped')),
                pages_crawled INTEGER DEFAULT 0,
                items_found INTEGER DEFAULT 0,
                max_depth INTEGER DEFAULT 3,
                error_message TEXT,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS crawled_pages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER REFERENCES crawl_sessions(id),
                url TEXT NOT NULL,
                title TEXT,
                depth INTEGER DEFAULT 0,
                status_code INTEGER,
                content_type TEXT,
                crawled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_media_type ON media_items(media_type);
            CREATE INDEX IF NOT EXISTS idx_media_url ON media_items(url);
            CREATE INDEX IF NOT EXISTS idx_crawl_status ON crawl_sessions(status);
        """)
        conn.commit()
        self._initialized = True
        logger.info("✓ Database initialized")

    # ━━━ Media Items CRUD ━━━

    def add_media_item(
        self,
        media_type: str,
        title: str = None,
        description: str = None,
        url: str = None,
        source_url: str = None,
        file_path: str = None,
        thumbnail_path: str = None,
        file_size: int = 0,
        width: int = None,
        height: int = None,
        duration: float = None,
        keywords: str = None,
    ) -> int:
        """Insert a new media item and return its ID."""
        conn = self._get_connection()
        cursor = conn.execute(
            """INSERT INTO media_items
            (media_type, title, description, url, source_url, file_path,
             thumbnail_path, file_size, width, height, duration, keywords)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (media_type, title, description, url, source_url, file_path,
             thumbnail_path, file_size, width, height, duration, keywords),
        )
        conn.commit()
        item_id = cursor.lastrowid
        logger.debug(f"Added media item #{item_id}: {media_type} - {title or url}")
        return item_id

    def get_media_item(self, item_id: int) -> Optional[dict]:
        """Retrieve a single media item by ID."""
        conn = self._get_connection()
        row = conn.execute("SELECT * FROM media_items WHERE id = ?", (item_id,)).fetchone()
        return dict(row) if row else None

    def get_media_items(
        self,
        media_type: str = None,
        limit: int = 50,
        offset: int = 0,
        search_query: str = None,
    ) -> list[dict]:
        """Retrieve media items with optional filtering."""
        conn = self._get_connection()
        query = "SELECT * FROM media_items WHERE 1=1"
        params = []

        if media_type:
            query += " AND media_type = ?"
            params.append(media_type)

        if search_query:
            query += " AND (title LIKE ? OR description LIKE ? OR keywords LIKE ?)"
            like = f"%{search_query}%"
            params.extend([like, like, like])

        query += " ORDER BY indexed_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def delete_media_item(self, item_id: int) -> bool:
        """Delete a media item by ID."""
        conn = self._get_connection()
        cursor = conn.execute("DELETE FROM media_items WHERE id = ?", (item_id,))
        conn.commit()
        return cursor.rowcount > 0

    def get_item_count(self, media_type: str = None) -> int:
        """Get total count of indexed items."""
        conn = self._get_connection()
        if media_type:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM media_items WHERE media_type = ?",
                (media_type,),
            ).fetchone()
        else:
            row = conn.execute("SELECT COUNT(*) as cnt FROM media_items").fetchone()
        return row["cnt"]

    def get_stats(self) -> dict:
        """Get database statistics."""
        conn = self._get_connection()
        total = conn.execute("SELECT COUNT(*) as cnt FROM media_items").fetchone()["cnt"]
        by_type = {}
        for row in conn.execute(
            "SELECT media_type, COUNT(*) as cnt FROM media_items GROUP BY media_type"
        ).fetchall():
            by_type[row["media_type"]] = row["cnt"]

        crawl_sessions = conn.execute("SELECT COUNT(*) as cnt FROM crawl_sessions").fetchone()["cnt"]

        return {
            "total_items": total,
            "by_type": by_type,
            "crawl_sessions": crawl_sessions,
        }

    # ━━━ Crawl Sessions ━━━

    def create_crawl_session(self, start_url: str, max_depth: int = 3) -> int:
        """Create a new crawl session and return its ID."""
        conn = self._get_connection()
        cursor = conn.execute(
            "INSERT INTO crawl_sessions (start_url, max_depth) VALUES (?, ?)",
            (start_url, max_depth),
        )
        conn.commit()
        return cursor.lastrowid

    def update_crawl_session(
        self,
        session_id: int,
        status: str = None,
        pages_crawled: int = None,
        items_found: int = None,
        error_message: str = None,
    ):
        """Update crawl session status."""
        conn = self._get_connection()
        updates = []
        params = []

        if status:
            updates.append("status = ?")
            params.append(status)
            if status in ("completed", "failed", "stopped"):
                updates.append("completed_at = ?")
                params.append(datetime.utcnow().isoformat())

        if pages_crawled is not None:
            updates.append("pages_crawled = ?")
            params.append(pages_crawled)

        if items_found is not None:
            updates.append("items_found = ?")
            params.append(items_found)

        if error_message:
            updates.append("error_message = ?")
            params.append(error_message)

        if updates:
            params.append(session_id)
            conn.execute(
                f"UPDATE crawl_sessions SET {', '.join(updates)} WHERE id = ?",
                params,
            )
            conn.commit()

    def get_crawl_session(self, session_id: int) -> Optional[dict]:
        """Get crawl session details."""
        conn = self._get_connection()
        row = conn.execute("SELECT * FROM crawl_sessions WHERE id = ?", (session_id,)).fetchone()
        return dict(row) if row else None

    def get_active_crawl_sessions(self) -> list[dict]:
        """Get all running crawl sessions."""
        conn = self._get_connection()
        rows = conn.execute(
            "SELECT * FROM crawl_sessions WHERE status IN ('pending', 'running') ORDER BY started_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def add_crawled_page(
        self,
        session_id: int,
        url: str,
        title: str = None,
        depth: int = 0,
        status_code: int = None,
        content_type: str = None,
    ) -> int:
        """Record a crawled page."""
        conn = self._get_connection()
        cursor = conn.execute(
            """INSERT INTO crawled_pages (session_id, url, title, depth, status_code, content_type)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (session_id, url, title, depth, status_code, content_type),
        )
        conn.commit()
        return cursor.lastrowid

    def is_url_crawled(self, session_id: int, url: str) -> bool:
        """Check if a URL has already been crawled in this session."""
        conn = self._get_connection()
        row = conn.execute(
            "SELECT 1 FROM crawled_pages WHERE session_id = ? AND url = ?",
            (session_id, url),
        ).fetchone()
        return row is not None


# Singleton instance
database = Database()
