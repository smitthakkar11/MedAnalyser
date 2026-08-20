"""Provider selection."""

from __future__ import annotations

from functools import lru_cache

from app.core.config import Settings, get_settings
from app.services.storage.base import StorageService
from app.services.storage.local import LocalStorageProvider


def build_storage_service(settings: Settings | None = None) -> StorageService:
    """Return the configured storage provider.

    Adding S3 means adding a branch here and a provider module; nothing that
    stores or reads a report changes.
    """
    settings = settings or get_settings()
    provider = settings.storage_provider.lower()

    if provider == "local":
        return LocalStorageProvider(settings.file_storage_path)
    raise ValueError(
        f"Unknown STORAGE_PROVIDER {settings.storage_provider!r}. Supported: 'local'."
    )


@lru_cache(maxsize=1)
def get_storage_service() -> StorageService:
    """The process-wide storage service."""
    return build_storage_service()
