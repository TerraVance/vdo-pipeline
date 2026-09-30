from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import projects, prompt, images, video
from app.core.database import get_supabase

app = FastAPI(
    title="Interactive AI Video Generation Pipeline API",
    description="API for managing the AI video generation workflow",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — allow Next.js dev server and all Vercel preview/production domains
# Note: allow_origins does NOT support wildcards — use allow_origin_regex instead
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https://.*\.vercel\.app|http://localhost:(3000|3001|3003|8001)",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register all routers ─────────────────────────────────────────────
app.include_router(projects.router)
app.include_router(prompt.router)
app.include_router(images.router)
app.include_router(video.router)


# ── Health checks ────────────────────────────────────────────────────
@app.get("/")
def root():
    return {"message": "Interactive AI Video Generation Pipeline API is running"}


@app.get("/api/v1/health")
def health_check():
    return {"status": "ok"}


@app.get("/api/v1/health/db")
def db_health_check():
    """Stage 2.6 — Verify Supabase connection is live."""
    try:
        db = get_supabase()
        # Run a lightweight query against our projects table
        result = db.table("projects").select("id").limit(1).execute()
        return {"status": "ok", "supabase": "connected"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
