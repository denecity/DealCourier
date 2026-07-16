"""FastAPI application setup."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from dealcourier.web.routers import dashboard, config, scheduler, prompts, logs

FRONTEND_DIR = Path(__file__).parent / "frontend"

app = FastAPI(title="DealCourier", version="2.0.0")

# Register API routers
app.include_router(dashboard.router, prefix="/api")
app.include_router(config.router, prefix="/api")
app.include_router(scheduler.router, prefix="/api")
app.include_router(prompts.router, prefix="/api")
app.include_router(logs.router, prefix="/api")

# Serve static files (CSS, JS)
static_dir = FRONTEND_DIR / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def index():
    """Serve the dashboard HTML."""
    index_file = FRONTEND_DIR / "templates" / "index.html"
    if index_file.exists():
        from fastapi.responses import HTMLResponse

        return HTMLResponse(index_file.read_text(encoding="utf-8"))
    return {"message": "DealCourier API is running. Frontend not found."}


@app.get("/health")
async def health():
    return {"status": "ok"}
