"""Aggregate API router.

Every resource router is mounted here; `main.py` mounts this one under the
configured API prefix. Adding a resource means touching exactly this file.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import auth, health

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
