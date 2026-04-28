"""
main.py
-------
FastAPI application entrypoint for DevIQ — AI Developer Intelligence Platform.

Registers:
  - /webhook/github  → GitHub webhook handler (PR reviews)
  - /docs/*          → Documentation generator endpoints
  - /health          → Health check
  - /reviews         → Review history

Run with:
  uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.database import init_db
from config.settings import get_settings
from utils.logger import setup_logging
from github.webhook import router as webhook_router
from utils.doc_router import router as doc_router

settings = get_settings()
setup_logging(debug=settings.debug)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle management."""
    logger.info("🚀 DevIQ starting up...")
    await init_db()
    logger.info("✅ Database initialised")
    yield
    logger.info("🛑 DevIQ shutting down...")


app = FastAPI(
    title="DevIQ — AI Developer Intelligence Platform",
    description=(
        "AI-powered code review and documentation generator. "
        "Integrates with GitHub via webhooks. "
        "Uses NVIDIA NIM multi-agent review pipeline + RAG."
    ),
    version="1.0.0",
    docs_url="/api/docs",      # Swagger UI
    redoc_url="/api/redoc",    # ReDoc
    lifespan=lifespan,
)

# CORS – allow all origins for development (tighten for production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(webhook_router)
app.include_router(doc_router)


# ------------------------------------------------------------------
# Additional endpoints
# ------------------------------------------------------------------

@app.get("/health", tags=["system"])
async def health():
    """Health check endpoint for Render/Railway/etc."""
    return {
        "status": "healthy",
        "service": "DevIQ",
        "version": "1.0.0",
        "nim_model": settings.nim_review_model,
    }


@app.get("/reviews", tags=["reviews"])
async def list_reviews(limit: int = 20, offset: int = 0):
    """List recent PR review records from the database."""
    from config.database import get_db
    async with get_db() as db:
        rows = await db.execute(
            "SELECT id, repo_full, pr_number, status, created_at FROM reviews "
            "ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        results = await rows.fetchall()
        return [dict(r) for r in results]


@app.get("/reviews/{review_id}", tags=["reviews"])
async def get_review(review_id: int):
    """Get a specific review with all its findings."""
    from config.database import get_db
    async with get_db() as db:
        row = await (await db.execute(
            "SELECT * FROM reviews WHERE id=?", (review_id,)
        )).fetchone()
        if not row:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Review not found")

        comments = await (await db.execute(
            "SELECT * FROM review_comments WHERE review_id=? ORDER BY severity",
            (review_id,),
        )).fetchall()

        return {
            "review": dict(row),
            "findings": [dict(c) for c in comments],
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.debug,
        log_level="debug" if settings.debug else "info",
    )
