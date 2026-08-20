"""Health-check service.

Kept out of the route handler so that readiness probing can be reused (startup
checks, CLI diagnostics) and unit-tested without HTTP.
"""

from __future__ import annotations

import logging
import time

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.health import ComponentStatus, DependencyHealth

logger = logging.getLogger(__name__)

#: Extensions the application requires to be installed in the database.
REQUIRED_EXTENSIONS = ("vector",)


async def check_database(session: AsyncSession) -> DependencyHealth:
    """Verify the database is reachable and required extensions are installed."""
    started = time.perf_counter()
    try:
        await session.execute(text("SELECT 1"))
        result = await session.execute(
            text("SELECT extname FROM pg_extension WHERE extname = ANY(:names)").bindparams(
                names=list(REQUIRED_EXTENSIONS)
            )
        )
        installed = {row[0] for row in result}
    except Exception as exc:  # noqa: BLE001 — health probes report, never raise.
        logger.warning("Database health probe failed", extra={"error": type(exc).__name__})
        return DependencyHealth(
            name="database",
            status=ComponentStatus.UNAVAILABLE,
            detail="Database is unreachable.",
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
        )

    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    missing = sorted(set(REQUIRED_EXTENSIONS) - installed)
    if missing:
        return DependencyHealth(
            name="database",
            status=ComponentStatus.DEGRADED,
            detail=f"Missing required extension(s): {', '.join(missing)}. Run migrations.",
            latency_ms=latency_ms,
        )

    return DependencyHealth(name="database", status=ComponentStatus.OK, latency_ms=latency_ms)


def check_condition_model() -> DependencyHealth:
    """Report whether the trained condition model is loaded and usable.

    Degraded rather than unavailable when absent: the rest of the application —
    accounts, profiles, history — works fine without it, and a fresh checkout
    has no artifacts until training has been run once.
    """
    started = time.perf_counter()
    try:
        from app.services.ml.condition_prediction.model_loader import get_condition_model

        model = get_condition_model()
    except Exception as exc:  # noqa: BLE001 - health probes report, never raise
        logger.warning("Condition model unavailable", extra={"error": type(exc).__name__})
        return DependencyHealth(
            name="condition_model",
            status=ComponentStatus.DEGRADED,
            detail=(
                "Trained model not loaded. Run "
                "`python -m ml.training.train_condition_model` to produce artifacts."
            ),
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
        )

    return DependencyHealth(
        name="condition_model",
        status=ComponentStatus.OK,
        detail=f"{model.name} {model.version} ({len(model.labels)} conditions)",
        latency_ms=round((time.perf_counter() - started) * 1000, 2),
    )


def aggregate_status(dependencies: list[DependencyHealth]) -> ComponentStatus:
    """Reduce dependency statuses to a single overall status (worst wins)."""
    statuses = {dep.status for dep in dependencies}
    if ComponentStatus.UNAVAILABLE in statuses:
        return ComponentStatus.UNAVAILABLE
    if ComponentStatus.DEGRADED in statuses:
        return ComponentStatus.DEGRADED
    return ComponentStatus.OK
