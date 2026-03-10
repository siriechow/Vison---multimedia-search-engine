"""
Vison - Crawler API Routes
Endpoints for managing web crawl sessions.
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl

from app.crawler.crawler import crawler
from app.search.database import database

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/crawler", tags=["Crawler"])


class CrawlRequest(BaseModel):
    url: str
    max_depth: int = 3
    max_pages: int = 100


class CrawlResponse(BaseModel):
    message: str
    session_id: int | None = None
    status: dict


@router.post("/start", response_model=CrawlResponse)
async def start_crawl(request: CrawlRequest):
    """
    Start a new web crawling session.
    The crawler will discover and index multimedia content from the target URL.
    """
    if crawler.is_running:
        raise HTTPException(
            status_code=409,
            detail="A crawl is already in progress. Stop it first or wait for completion.",
        )

    result = crawler.start(
        url=request.url,
        max_depth=request.max_depth,
        max_pages=request.max_pages,
    )

    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    return CrawlResponse(
        message=result["message"],
        session_id=result.get("session_id"),
        status=result["status"],
    )


@router.get("/status")
async def get_crawler_status():
    """Get the current status of the crawler."""
    status = crawler.status

    # Also get recent sessions from DB
    active_sessions = database.get_active_crawl_sessions()

    return {
        "crawler": status,
        "active_sessions": active_sessions,
    }


@router.post("/stop")
async def stop_crawl():
    """Stop the currently active crawl session."""
    if not crawler.is_running:
        raise HTTPException(
            status_code=404,
            detail="No active crawl session to stop.",
        )

    result = crawler.stop()
    return result


@router.get("/sessions/{session_id}")
async def get_crawl_session(session_id: int):
    """Get details of a specific crawl session."""
    session = database.get_crawl_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session
