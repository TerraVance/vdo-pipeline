from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import projects, prompt, images, chat
from app.core.database import get_supabase
from app.core.config import get_settings
from app.core.logging import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up Interactive AI Video Generation Pipeline API...")
    # Verify DB connectivity on startup
    try:
        db = get_supabase()
        db.table("projects").select("id").limit(1).execute()
        logger.info("Supabase database connection verified successfully.")
    except Exception as e:
        logger.warning(f"Initial Supabase connectivity check warning: {e}")
    yield
    logger.info("Shutting down API server...")


app = FastAPI(
    title="Interactive AI Video Generation Pipeline API",
    description="API for managing the AI video generation workflow",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS — allow Next.js dev server, Vercel, Render, Railway, Cloudflare Pages, and configured domains
_settings = get_settings()
_extra_origins = [o.strip() for o in _settings.allowed_origins.split(",") if o.strip()]
_local_origins = ["http://localhost:3000", "http://localhost:3001", "http://localhost:3003", "http://localhost:8001"]
_allowed_origins = list(set(_local_origins + _extra_origins))

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_origin_regex=r"https://.*(\.vercel\.app|\.onrender\.com|\.railway\.app|\.pages\.dev)",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register all routers ─────────────────────────────────────────────
# Note: prompt.router must be registered before projects.router so that
# static paths like /api/v1/projects/gemini-models are matched before dynamic /{project_id}
app.include_router(prompt.router)
app.include_router(projects.router)
app.include_router(images.router)
app.include_router(chat.router)


# ── Health checks ────────────────────────────────────────────────────
@app.get("/")
def root():
    return {"message": "Interactive AI Video Generation Pipeline API is running"}


@app.get("/api/v1/health")
def health_check():
    return {"status": "ok"}


@app.get("/api/v1/health/db")
def db_health_check():
    """Verify Supabase connection is live."""
    try:
        db = get_supabase()
        db.table("projects").select("id").limit(1).execute()
        return {"status": "ok", "supabase": "connected"}
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {"status": "error", "detail": str(e)}

