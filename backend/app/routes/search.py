"""
Vison - Search API Routes
Endpoints for reverse multimedia search and text-based search.
"""

import logging
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, File, UploadFile, Query, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.ml.feature_extractor import (
    extract_image_features,
    extract_audio_features,
    extract_video_features,
)
from app.ml.text_analyzer import compute_text_similarity
from app.search.vector_store import vector_store
from app.search.database import database

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/search", tags=["Search"])


class SearchResult(BaseModel):
    id: int
    media_type: str
    title: str | None
    description: str | None
    url: str | None
    source_url: str | None
    thumbnail_path: str | None
    similarity_score: float
    keywords: str | None


class SearchResponse(BaseModel):
    query_type: str
    total_results: int
    results: list[SearchResult]
    processing_time_ms: float


@router.post("/upload", response_model=SearchResponse)
async def search_by_upload(
    file: UploadFile = File(...),
    media_type: str = Query(None, description="Force media type: image, audio, or video"),
    top_k: int = Query(20, ge=1, le=100),
):
    """
    Upload an image, audio, or video file to find similar content in the index.
    This is the core reverse multimedia search endpoint.
    """
    import time
    start_time = time.time()

    # Determine media type from file extension if not specified
    if media_type is None:
        ext = Path(file.filename or "").suffix.lower()
        if ext in settings.SUPPORTED_IMAGE_TYPES:
            media_type = "image"
        elif ext in settings.SUPPORTED_AUDIO_TYPES:
            media_type = "audio"
        elif ext in settings.SUPPORTED_VIDEO_TYPES:
            media_type = "video"
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {ext}. Supported: images ({', '.join(settings.SUPPORTED_IMAGE_TYPES)}), audio ({', '.join(settings.SUPPORTED_AUDIO_TYPES)}), video ({', '.join(settings.SUPPORTED_VIDEO_TYPES)})",
            )

    # Save uploaded file temporarily
    upload_path = settings.UPLOAD_DIR / f"{uuid.uuid4().hex}_{file.filename}"
    try:
        with open(upload_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # Extract features
        features = None
        if media_type == "image":
            features = extract_image_features(upload_path)
        elif media_type == "audio":
            features = extract_audio_features(upload_path)
        elif media_type == "video":
            features = extract_video_features(upload_path)

        if features is None:
            raise HTTPException(
                status_code=422,
                detail="Failed to extract features from the uploaded file. The file may be corrupted or in an unsupported format.",
            )

        # Search vector store
        raw_results = vector_store.search(media_type, features, top_k=top_k)

        # Fetch metadata for results
        results = []
        for item_id, score in raw_results:
            item = database.get_media_item(item_id)
            if item:
                results.append(SearchResult(
                    id=item["id"],
                    media_type=item["media_type"],
                    title=item.get("title"),
                    description=item.get("description"),
                    url=item.get("url"),
                    source_url=item.get("source_url"),
                    thumbnail_path=item.get("thumbnail_path"),
                    similarity_score=round(score, 4),
                    keywords=item.get("keywords"),
                ))

        elapsed = (time.time() - start_time) * 1000

        return SearchResponse(
            query_type=f"reverse_{media_type}_search",
            total_results=len(results),
            results=results,
            processing_time_ms=round(elapsed, 2),
        )

    finally:
        # Cleanup upload
        upload_path.unlink(missing_ok=True)


@router.get("/text", response_model=SearchResponse)
async def search_by_text(
    q: str = Query(..., min_length=1, description="Search query"),
    media_type: str = Query(None, description="Filter by media type"),
    top_k: int = Query(20, ge=1, le=100),
):
    """
    Text-based search across indexed media metadata.
    Searches titles, descriptions, and keywords using NLP similarity.
    """
    import time
    start_time = time.time()

    # Get items from database using text search
    items = database.get_media_items(
        media_type=media_type,
        limit=200,
        search_query=q,
    )

    if not items:
        return SearchResponse(
            query_type="text_search",
            total_results=0,
            results=[],
            processing_time_ms=round((time.time() - start_time) * 1000, 2),
        )

    # Compute text similarity scores
    documents = [
        f"{item.get('title', '')} {item.get('description', '')} {item.get('keywords', '')}"
        for item in items
    ]
    scores = compute_text_similarity(q, documents)

    # Combine items with scores and sort
    scored_items = sorted(
        zip(items, scores),
        key=lambda x: x[1],
        reverse=True,
    )[:top_k]

    results = [
        SearchResult(
            id=item["id"],
            media_type=item["media_type"],
            title=item.get("title"),
            description=item.get("description"),
            url=item.get("url"),
            source_url=item.get("source_url"),
            thumbnail_path=item.get("thumbnail_path"),
            similarity_score=round(score, 4),
            keywords=item.get("keywords"),
        )
        for item, score in scored_items
        if score > 0.01
    ]

    elapsed = (time.time() - start_time) * 1000

    return SearchResponse(
        query_type="text_search",
        total_results=len(results),
        results=results,
        processing_time_ms=round(elapsed, 2),
    )


@router.get("/results/{item_id}")
async def get_search_result(item_id: int):
    """Get detailed information about a specific media item."""
    item = database.get_media_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item
