"""FastAPI Application Entrypoint for CAT Operator Decision Loop.

Includes:
  - CORS middleware for React / Vite frontend
  - Lifespan startup model loading
  - Error handlers for 404, 422, and 503 (model not loaded)
  - Operator and Dashboard routers
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.deviation_engine.deviation import load_reference_artifacts
from app.prediction.task_time_model import load_task_time_artifacts
from app.routers.dashboard import router as dashboard_router
from app.routers.operators import router as operators_router
from app.routers.simulate import router as simulate_router

logger = logging.getLogger("cat_decision_loop")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

_MODELS_LOADED: bool = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager — loads ML models at startup."""
    global _MODELS_LOADED
    try:
        load_reference_artifacts()
        load_task_time_artifacts()
        _MODELS_LOADED = True
        logger.info("Successfully loaded reference and task-time models at startup.")
    except Exception as exc:
        logger.warning(
            "Model artifacts could not be fully loaded at startup: %s. "
            "Ensure training scripts have been run.",
            exc,
        )
        _MODELS_LOADED = False
    yield


app = FastAPI(
    title="CAT Operator Decision Loop API",
    description="Intelligent Operator Decision Loop Backend — Synthetic Data Hackathon Demo",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS Configuration ───────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permits local React / Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Exception Handlers ─────────────────────────────────────────────────────
@app.exception_handler(FileNotFoundError)
async def handle_models_not_found(request: Request, exc: FileNotFoundError):
    """503 Service Unavailable when required ML model artifacts are missing."""
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "error": "ModelNotLoaded",
            "detail": "ML model artifacts are missing. Please run the model training script first.",
            "path": str(request.url.path),
        },
    )


@app.exception_handler(RequestValidationError)
async def handle_validation_error(request: Request, exc: RequestValidationError):
    """Custom 422 validation error handler returning clear structured JSON."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "ValidationError",
            "detail": exc.errors(),
            "path": str(request.url.path),
        },
    )


@app.exception_handler(HTTPException)
async def handle_http_exception(request: Request, exc: HTTPException):
    """Standard HTTPException handler."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "HTTPException",
            "detail": exc.detail,
            "path": str(request.url.path),
        },
    )


# ── Routers ─────────────────────────────────────────────────────────────────
app.include_router(operators_router)
app.include_router(dashboard_router)
app.include_router(simulate_router)


@app.get("/health", tags=["system"])
def health_check() -> dict[str, Any]:
    """Health check endpoint indicating model loading status."""
    return {
        "status": "healthy",
        "models_loaded": _MODELS_LOADED,
        "is_synthetic": True,
        "demo_mode": settings.demo_mode,
    }
