"""
DMM Console – FastAPI application entry point.

Run:
    sudo uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

Then open http://localhost:8000 in a browser.
"""

from __future__ import annotations

import logging
import os
from fastapi import FastAPI

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .api.routes    import router
from .api.websocket import websocket_router

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="DMM Console",
    description="Web-based DMM control panel (GPIB / LAN / USB)",
    version="0.1.0",
)

# Allow all origins in development (restrict in production via nginx)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router,           prefix="/api")
app.include_router(websocket_router)

# ---------------------------------------------------------------------------
# Serve built frontend
# ---------------------------------------------------------------------------

_DIST = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")

if os.path.isdir(_DIST):
    # Serve Vite build output
    app.mount("/assets", StaticFiles(directory=os.path.join(_DIST, "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str) -> FileResponse:
        return FileResponse(os.path.join(_DIST, "index.html"))
else:
    @app.get("/", include_in_schema=False)
    async def dev_notice():
        return {
            "message": "Frontend not built yet.",
            "hint": "cd frontend && npm install && npm run build",
        }
