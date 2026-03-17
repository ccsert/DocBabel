import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import init_db
from app.services.babeldoc_assets import get_offline_assets_status
from app.services.babeldoc_assets import ensure_offline_assets_ready
from app.services.babeldoc_assets import restore_offline_assets_package
from app.services.queue import translation_queue
from app.api import auth, tasks, glossaries, models, admin, files


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
    os.makedirs(settings.BABELDOC_OFFLINE_EXPORT_DIR, exist_ok=True)
    if settings.BABELDOC_OFFLINE_ASSETS_PACKAGE:
        await restore_offline_assets_package(settings.BABELDOC_OFFLINE_ASSETS_PACKAGE)
    if settings.BABELDOC_OFFLINE_MODE or settings.BABELDOC_PRECHECK_ASSETS_ON_STARTUP:
        ensure_offline_assets_ready(force=True)
    await init_db()
    await translation_queue.start()
    yield
    # Shutdown
    await translation_queue.stop()


app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router, prefix="/api")
app.include_router(tasks.router, prefix="/api")
app.include_router(files.router, prefix="/api")
app.include_router(glossaries.router, prefix="/api")
app.include_router(models.router, prefix="/api")
app.include_router(admin.router, prefix="/api")


@app.get("/api/health")
async def health():
    assets_status = get_offline_assets_status()
    return {
        "status": "ok",
        "babeldoc_offline_mode": settings.BABELDOC_OFFLINE_MODE,
        "babeldoc_offline_assets_package": bool(settings.BABELDOC_OFFLINE_ASSETS_PACKAGE),
        "babeldoc_offline_asset_profile": assets_status["profile"],
        "babeldoc_assets_ready": assets_status["ready"],
        "babeldoc_assets_missing_files": assets_status["missing_files"],
    }
