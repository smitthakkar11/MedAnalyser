"""MedAnalyser FastAPI application factory."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.router import api_router
from app.core.config import Environment, Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware, SecurityHeadersMiddleware

logger = logging.getLogger(__name__)

DESCRIPTION = """
MedAnalyser is an AI-assisted health assessment platform.

**This API is an educational/portfolio project. It does not provide medical
diagnosis and is not a substitute for a licensed medical professional.**
""".strip()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application startup/shutdown.

    Startup deliberately does not block on the database: the process should come
    up and report *not ready* rather than crash-loop while Postgres starts.
    """
    settings: Settings = app.state.settings
    logger.info(
        "MedAnalyser API starting",
        extra={"environment": settings.environment.value, "version": __version__},
    )
    _warm_up_models(settings)
    yield
    from app.db.session import dispose_engine

    await dispose_engine()
    logger.info("MedAnalyser API stopped")


def _warm_up_models(settings: Settings) -> None:
    """Load ML artifacts once at startup so no request pays for it.

    A missing model is not fatal by default: everything except prediction still
    works, and a fresh checkout has no artifacts until training has been run.
    Set `ML_REQUIRE_MODEL=true` in production to refuse to start without one.
    """
    from app.services.ml.condition_prediction.model_loader import (
        ModelUnavailableError,
        get_condition_model,
    )

    try:
        model = get_condition_model()
    except ModelUnavailableError as exc:
        if settings.ml_require_model:
            raise
        logger.warning(
            "Starting without a condition model; prediction will be unavailable",
            extra={"reason": str(exc)},
        )
        return
    logger.info(
        "Condition model ready",
        extra={"model_name": model.name, "model_version": model.version},
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build and configure the FastAPI application."""
    settings = settings or get_settings()
    configure_logging(
        settings.log_level,
        json_output=settings.environment is not Environment.DEVELOPMENT,
    )

    app = FastAPI(
        title=settings.app_name,
        description=DESCRIPTION,
        version=__version__,
        lifespan=lifespan,
        # Interactive docs are a development convenience, not a production feature.
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None if settings.is_production else "/redoc",
        openapi_url=None if settings.is_production else "/openapi.json",
    )
    app.state.settings = settings

    # Middleware runs bottom-up: security headers are applied first on the way
    # out, request context wraps everything so the id covers CORS failures too.
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(RequestContextMiddleware)

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_prefix)

    return app


app = create_app()
