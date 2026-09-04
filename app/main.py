"""
Umbra Assistant backend — FastAPI app factory.

Run locally with:  uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import UmbraError
from app.core.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        debug=settings.DEBUG,
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],  # Vite dev server
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
            "using_mock_vectorstore": settings.use_mock_vectorstore,
            "using_mock_embeddings": settings.use_mock_embeddings,
        }

    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    logger.info(
        "Umbra backend started | env=%s mock_vectorstore=%s mock_embeddings=%s",
        settings.APP_ENV, settings.use_mock_vectorstore, settings.use_mock_embeddings,
    )
    return app


app = create_app()
