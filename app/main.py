import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import engine
from app.models import models  # noqa: F401 — registers all tables
from app.database import Base
from app.routers import auth, user, glucose, insights

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup (use Alembic migrations for production schema changes)
    Base.metadata.create_all(bind=engine)
    Path(settings.LOCAL_UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    logger.info("GlucoSnap API ready")
    yield


app = FastAPI(
    title="GlucoSnap API",
    version="1.0.0",
    description="Backend for the GlucoSnap glucose monitoring app",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# Tighten origins in production to your app's domain
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Static files (local image serving) ───────────────────────────────────────
if settings.STORAGE_BACKEND == "local":
    app.mount(
        "/static",
        StaticFiles(directory=settings.LOCAL_UPLOAD_DIR),
        name="static",
    )

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(user.router)
app.include_router(glucose.router)
app.include_router(insights.router)


@app.get("/", tags=["health"])
def root():
    return {"status": "ok", "service": "GlucoSnap API", "version": "1.0.0"}


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}
