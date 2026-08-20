"""The storage contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


class StorageError(RuntimeError):
    """Raised when a file cannot be stored, read or removed."""


@dataclass(frozen=True)
class StoredFile:
    """A file that has been written to storage.

    ``key`` is the provider-independent handle recorded in the database. It is
    never a path the client chose, and never something a client can supply.
    """

    key: str
    size_bytes: int
    content_type: str
    #: SHA-256 of the bytes, used to detect a duplicate upload without
    #: re-reading the file.
    checksum: str


@runtime_checkable
class StorageService(Protocol):
    """Stores and retrieves user files.

    Implementations must treat every key as untrusted input and refuse anything
    that escapes their own namespace.
    """

    async def save(
        self, *, owner_id: str, filename: str, content: bytes, content_type: str
    ) -> StoredFile:
        """Persist *content* and return its handle."""
        ...

    async def read(self, key: str) -> bytes:
        """Return the bytes stored under *key*."""
        ...

    async def delete(self, key: str) -> None:
        """Remove *key*. Deleting something absent is not an error."""
        ...

    async def exists(self, key: str) -> bool: ...
