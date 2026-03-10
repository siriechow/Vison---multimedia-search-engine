"""
Vison - Index Management API Routes
Endpoints for managing the search index.
"""

import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, File, UploadFile, Query, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.config import settings
from app.ml.feature_extractor import (
    extract_image_features,
    extract_audio_features,
    extract_video_features,
    generate_thumbnail,
)
from app.ml.text_analyzer import extract_keywords
from app.search.vector_store import vector_store
from app.search.database import database

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/index", tags=["Index"])


class IndexStats(BaseModel):
    total_items: int
    by_type: dict
    vector_store: dict
    crawl_sessions: int


class AddItemResponse(BaseModel):
    id: int
    media_type: str
    message: str


@router.get("/stats", response_model=IndexStats)
async def get_index_stats():
    """Get statistics about the search index."""
    db_stats = database.get_stats()
    vs_stats = vector_store.get_stats()

    return IndexStats(
        total_items=db_stats["total_items"],
        by_type=db_stats.get("by_type", {}),
        vector_store=vs_stats,
        crawl_sessions=db_stats.get("crawl_sessions", 0),
    )


@router.post("/add", response_model=AddItemResponse)
async def add_item(
    file: UploadFile = File(...),
    title: str = Query("", description="Title for the media item"),
    description: str = Query("", description="Description"),
    media_type: str = Query(None, description="Force media type"),
):
    """Manually add a media item to the index."""
    # Determine media type
    if media_type is None:
        ext = Path(file.filename or "").suffix.lower()
        if ext in settings.SUPPORTED_IMAGE_TYPES:
            media_type = "image"
        elif ext in settings.SUPPORTED_AUDIO_TYPES:
            media_type = "audio"
        elif ext in settings.SUPPORTED_VIDEO_TYPES:
            media_type = "video"
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    # Save file
    filename = f"{uuid.uuid4().hex}_{file.filename}"
    type_dir = settings.MEDIA_DIR / f"{media_type}s"
    type_dir.mkdir(parents=True, exist_ok=True)
    file_path = type_dir / filename

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    # Extract features
    features = None
    if media_type == "image":
        features = extract_image_features(file_path)
    elif media_type == "audio":
        features = extract_audio_features(file_path)
    elif media_type == "video":
        features = extract_video_features(file_path)

    if features is None:
        file_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail="Feature extraction failed")

    # Generate thumbnail
    thumb_filename = f"{Path(filename).stem}_thumb.jpg"
    thumb_path = settings.THUMBNAILS_DIR / thumb_filename
    generate_thumbnail(file_path, thumb_path, media_type)

    # Extract keywords
    keywords_text = f"{title} {description}"
    keywords = ", ".join(extract_keywords(keywords_text, top_n=10))

    # Store in database
    item_id = database.add_media_item(
        media_type=media_type,
        title=title or file.filename,
        description=description,
        file_path=str(file_path),
        thumbnail_path=str(thumb_path) if thumb_path.exists() else None,
        file_size=len(content),
        keywords=keywords,
    )

    # Add to vector store
    vector_store.add(media_type, item_id, features)
    vector_store.save()

    return AddItemResponse(
        id=item_id,
        media_type=media_type,
        message=f"Successfully indexed {media_type} item #{item_id}",
    )


@router.delete("/{item_id}")
async def delete_item(item_id: int):
    """Remove an item from the index."""
    item = database.get_media_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    # Remove from vector store
    vector_store.remove(item["media_type"], item_id)

    # Remove files
    if item.get("file_path"):
        Path(item["file_path"]).unlink(missing_ok=True)
    if item.get("thumbnail_path"):
        Path(item["thumbnail_path"]).unlink(missing_ok=True)

    # Remove from database
    database.delete_media_item(item_id)
    vector_store.save()

    return {"message": f"Item #{item_id} removed from index"}


@router.get("/items")
async def list_items(
    media_type: str = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    q: str = Query(None, description="Search query"),
):
    """List indexed items with optional filtering."""
    items = database.get_media_items(
        media_type=media_type,
        limit=limit,
        offset=offset,
        search_query=q,
    )
    total = database.get_item_count(media_type=media_type)

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/thumbnail/{item_id}")
async def get_thumbnail(item_id: int):
    """Serve the thumbnail for a media item."""
    item = database.get_media_item(item_id)
    if not item or not item.get("thumbnail_path"):
        raise HTTPException(status_code=404, detail="Thumbnail not found")

    thumb_path = Path(item["thumbnail_path"])
    if not thumb_path.exists():
        raise HTTPException(status_code=404, detail="Thumbnail file missing")

    return FileResponse(thumb_path, media_type="image/jpeg")


@router.get("/media/{item_id}")
async def get_media(item_id: int):
    """Serve the original media file for an item."""
    item = database.get_media_item(item_id)
    if not item or not item.get("file_path"):
        raise HTTPException(status_code=404, detail="Media file not found")

    file_path = Path(item["file_path"])
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Media file missing")

    # Determine content type
    content_types = {
        "image": "image/jpeg",
        "audio": "audio/mpeg",
        "video": "video/mp4",
    }
    ct = content_types.get(item["media_type"], "application/octet-stream")

    return FileResponse(file_path, media_type=ct)
