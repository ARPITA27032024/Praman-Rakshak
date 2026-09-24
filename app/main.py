from os import makedirs
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.config import settings
from app.api.health import router as health_router
from app.api.ocr import router as ocr_router
from app.api.classification import router as classification_router
from app.api.evaluation import router as evaluation_router
from app.api.kie import router as kie_router
from app.api.pii import router as pii_router
from app.api.redaction import router as redaction_router
from app.api.process import router as process_router

app = FastAPI(
    title=settings.APP_NAME,
    description="Digital Evidence & Document Management System Backend API",
    version="0.1.0",
)

# Ensure required storage directories exist
makedirs(settings.ORIGINALS_DIR, exist_ok=True)
makedirs(settings.REDACTED_DIR, exist_ok=True)

# Mount static files directory
static_dir = Path(__file__).parent / "static"
makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Include API routers
app.include_router(health_router)
app.include_router(ocr_router)
app.include_router(classification_router)
app.include_router(evaluation_router)
app.include_router(kie_router)
app.include_router(pii_router)
app.include_router(redaction_router)
app.include_router(process_router)


@app.get("/", response_class=FileResponse)
async def root():
    """Serve PRAMAAN RAKSHAK Demo Dashboard."""
    index_path = static_dir / "index.html"
    return FileResponse(str(index_path))
