"""
Vison - Multimedia Search Engine
FastAPI application entry point.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings, ensure_directories
from app.routes import search, crawler, index
from app.search.database import database
from app.search.vector_store import vector_store

# Configure logging
logging.basicConfig(
    level=logging.INFO if settings.DEBUG else logging.WARNING,
    format="%(asctime)s │ %(levelname)-8s │ %(name)-25s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("vison")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle: startup and shutdown."""
    # ── Startup ──
    logger.info("=" * 60)
    logger.info(f"  🔍 {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"  {settings.APP_DESCRIPTION}")
    logger.info("=" * 60)

    # Create directories
    ensure_directories()
    logger.info("✓ Data directories ready")

    # Initialize database
    database.initialize()

    # Initialize vector store
    vector_store.initialize()

    # Try to load ML models (non-blocking, lazy load on first use)
    try:
        from app.ml.feature_extractor import initialize_models
        initialize_models()
    except Exception as e:
        logger.warning(f"ML model preloading skipped: {e}")
        logger.info("Models will be loaded on first use")

    logger.info("✓ Vison is ready to serve requests")
    logger.info(f"  API docs: http://{settings.HOST}:{settings.PORT}/docs")

    yield

    # ── Shutdown ──
    logger.info("Shutting down Vison...")
    vector_store.save()
    logger.info("✓ Vector store saved")


# ── Create application ──
app = FastAPI(
    title=settings.APP_NAME,
    description=f"""
## {settings.APP_DESCRIPTION}

**Vison** is a research-oriented, open-source search engine for bringing reverse multimedia
search to small & mid-scale enterprises.

### Features
- 🖼️ **Reverse Image Search** — Upload an image, find visually similar content
- 🎵 **Audio Fingerprinting** — Search by audio similarity using MFCC analysis
- 🎬 **Video Search** — Find similar videos via keyframe feature extraction
- 📝 **Text Search** — NLP-powered text search across metadata
- 🕷️ **Web Crawler** — Selenium-based crawler for multimedia content discovery
- ⚡ **Intel OpenVINO** — Optimized inference on CPU hardware
    """,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS + ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Mount routes ──
app.include_router(search.router)
app.include_router(crawler.router)
app.include_router(index.router)

# ── Static files for thumbnails/media ──
ensure_directories()
app.mount("/static/thumbnails", StaticFiles(directory=str(settings.THUMBNAILS_DIR)), name="thumbnails")
app.mount("/static/media", StaticFiles(directory=str(settings.MEDIA_DIR)), name="media")


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint — API overview."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "description": settings.APP_DESCRIPTION,
        "docs": "/docs",
        "endpoints": {
            "search_upload": "POST /api/search/upload",
            "search_text": "GET /api/search/text?q=",
            "crawler_start": "POST /api/crawler/start",
            "crawler_status": "GET /api/crawler/status",
            "index_stats": "GET /api/index/stats",
            "health": "GET /api/health",
        },
    }


@app.get("/api/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    db_stats = database.get_stats()
    vs_stats = vector_store.get_stats()

    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "database": {
            "total_items": db_stats["total_items"],
            "by_type": db_stats.get("by_type", {}),
        },
        "vector_store": vs_stats,
    }
