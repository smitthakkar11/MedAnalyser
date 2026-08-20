"""Health and readiness endpoints.

`/health` is a liveness probe: it must never touch a dependency, so that an
outage of the database does not cause orchestrators to kill healthy processes.
`/health/ready` is a readiness probe and does check dependencies.
"""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from app import __version__
from app.api.deps import AppSettings, DbSession
from app.schemas.health import ComponentStatus, HealthResponse, ReadinessResponse
from app.services.health import (
    aggregate_status,
    check_condition_model,
    check_database,
)

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="Liveness probe")
async def health(settings: AppSettings) -> HealthResponse:
    """Report that the API process is running."""
    return HealthResponse(
        status=ComponentStatus.OK,
        app=settings.app_name,
        version=__version__,
        environment=settings.environment.value,
    )


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    summary="Readiness probe",
    responses={503: {"description": "One or more dependencies are unavailable."}},
)
async def readiness(
    settings: AppSettings,
    session: DbSession,
    response: Response,
) -> ReadinessResponse:
    """Report whether every dependency required to serve traffic is available."""
    dependencies = [await check_database(session), check_condition_model()]
    overall = aggregate_status(dependencies)

    if overall is ComponentStatus.UNAVAILABLE:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadinessResponse(
        status=overall,
        app=settings.app_name,
        version=__version__,
        environment=settings.environment.value,
        dependencies=dependencies,
    )
