"""Shared FastAPI dependencies."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_db_session


def get_app_settings(request: Request) -> Settings:
    """Return the settings the running app was built with.

    Reads `app.state.settings` rather than calling `get_settings()` directly, so
    that an app constructed via `create_app(custom_settings)` — as tests do —
    is actually served with those settings.
    """
    settings = getattr(request.app.state, "settings", None)
    return settings if isinstance(settings, Settings) else get_settings()


#: Request-scoped database session.
DbSession = Annotated[AsyncSession, Depends(get_db_session)]

#: Settings of the running application.
AppSettings = Annotated[Settings, Depends(get_app_settings)]
