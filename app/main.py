"""
Umbra Assistant backend — FastAPI app factory.

Run locally with:  uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import UmbraError
from app.core.logging import configure_logging, get_logger
from app.services.scheduler import create_scheduler

configure_logging()
logger = get_logger(__name__)


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        scheduler = None
        if settings.RETRY_SCHEDULER_ENABLED:
            scheduler = create_scheduler()
            scheduler.start()
            app.state.retry_scheduler = scheduler
            logger.info(
                "Ingestion retry scheduler started | interval=%ss batch_limit=%s",
                settings.RETRY_INTERVAL_SECONDS,
                settings.RETRY_BATCH_LIMIT,
            )
        try:
            yield
        finally:
            if scheduler is not None:
                scheduler.shutdown(wait=False)
                logger.info("Ingestion retry scheduler stopped")

    app = FastAPI(
        title=settings.APP_NAME,
        debug=settings.DEBUG,
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.FRONTEND_ORIGINS,  # Vite dev server
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(UmbraError)
    async def umbra_error_handler(request: Request, exc: UmbraError):
        logger.error("UmbraError on %s: %s", request.url.path, exc.message)
        return JSONResponse(content={"detail": exc.message}, status_code=exc.status_code,)

    @app.get("/health")
    async def health():
        return {
            "status": "ok",
            "app": settings.APP_NAME,
            "env": settings.APP_ENV,
        }

    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    logger.info(
        "Umbra backend started | env=%s",
        settings.APP_ENV,
    )
    return app


app = create_app()
