"""
Promoter Performance Tracker — FastAPI Application Entry Point.

Initializes the database, configures CORS, mounts static file serving
for uploaded images, and registers all API route modules.

Run with:
  uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from database import init_db
from routes import upload, leaderboard, admin
from config import UPLOAD_DIR
from worker import start_worker

# ──────────────────────────────────────────────
# Initialize database tables on startup
# ──────────────────────────────────────────────
init_db()

# ──────────────────────────────────────────────
# Start background OCR worker thread
# ──────────────────────────────────────────────
start_worker()

# ──────────────────────────────────────────────
# Create FastAPI application
# ──────────────────────────────────────────────
app = FastAPI(
    title="Promoter Performance Tracker",
    description="Track promoter performance with OCR-based anti-fraud detection.",
    version="1.0.0",
)


@app.on_event("startup")
def preload_ocr_engine():
    """Pre-warm the OCR engine on startup in a background thread so it doesn't block the health check."""
    try:
        from ocr_service import get_ocr_engine
        import threading
        print("[Startup] Triggering eager loading of RapidOCR engine in background...")
        threading.Thread(target=get_ocr_engine, daemon=True).start()
    except Exception as e:
        print(f"[Startup] Failed to eager load OCR engine: {e}")

# ──────────────────────────────────────────────
# CORS — Allow frontend dev server to call API
# In production, restrict allow_origins to your domain.
# ──────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────────
# Static file serving for uploaded images
# Accessible at: GET /uploads/{path_to_image}
# ──────────────────────────────────────────────
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

# ──────────────────────────────────────────────
# Register API routes
# ──────────────────────────────────────────────
app.include_router(upload.router, prefix="/api", tags=["Upload"])
app.include_router(leaderboard.router, prefix="/api", tags=["Leaderboard"])
app.include_router(admin.router, prefix="/api", tags=["Admin"])


@app.get("/api/health")
async def health_check():
    """Simple health check endpoint for monitoring."""
    return {"status": "ok", "message": "Promoter Tracker API is running."}
