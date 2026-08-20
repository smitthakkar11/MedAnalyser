"""Schemas for the health and readiness endpoints."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class ComponentStatus(StrEnum):
    """Health of a single dependency."""

    OK = "ok"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


class DependencyHealth(BaseModel):
    """Health of one external dependency."""

    name: str = Field(description="Dependency identifier, e.g. 'database'.")
    status: ComponentStatus
    detail: str | None = Field(
        default=None,
        description="Short human-readable explanation when not 'ok'.",
    )
    latency_ms: float | None = Field(
        default=None, description="Round-trip time of the health probe."
    )


class HealthResponse(BaseModel):
    """Liveness response — the process is up and serving requests."""

    status: ComponentStatus
    app: str
    version: str
    environment: str


class ReadinessResponse(BaseModel):
    """Readiness response — the process can serve real traffic."""

    status: ComponentStatus
    app: str
    version: str
    environment: str
    dependencies: list[DependencyHealth]
