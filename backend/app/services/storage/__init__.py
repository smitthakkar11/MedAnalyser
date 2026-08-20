"""File storage behind a provider interface.

Business logic depends on :class:`StorageService`, never on the filesystem or a
cloud SDK, so moving uploaded reports to object storage later is a new provider
plus one environment variable — not a change to the report pipeline.
"""

from app.services.storage.base import (
    StorageError,
    StorageService,
    StoredFile,
)
from app.services.storage.factory import build_storage_service
from app.services.storage.local import LocalStorageProvider

__all__ = [
    "LocalStorageProvider",
    "StorageError",
    "StorageService",
    "StoredFile",
    "build_storage_service",
]
