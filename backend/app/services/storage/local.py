"""Filesystem storage for development.

Layout is ``<root>/<owner_id>/<uuid><ext>``. Two properties matter:

* **The stored name is generated, never the user's.** An uploaded filename is
  attacker-controlled: it can contain path separators, traversal sequences,
  null bytes, or names the OS treats specially. The original is kept in the
  database as a display label only, and never touches the filesystem.
* **Every read is confined to the root.** Keys are re-validated on the way back
  in, so even a corrupted database row cannot make the API read `/etc/passwd`.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from functools import partial
from pathlib import Path

import anyio

from app.services.storage.base import StorageError, StoredFile

#: Extensions this provider will write. Anything else is stored without one.
_SAFE_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".txt"}

#: A key is exactly `<owner>/<name>` with no traversal and no nesting.
_KEY_PATTERN = re.compile(r"^[0-9a-fA-F-]{36}/[0-9a-fA-F-]{36}(\.[a-z0-9]{1,8})?$")


class LocalStorageProvider:
    """Stores files under a root directory on the local filesystem."""

    def __init__(self, root: Path) -> None:
        self._root = root.expanduser().resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def root(self) -> Path:
        return self._root

    async def save(
        self, *, owner_id: str, filename: str, content: bytes, content_type: str
    ) -> StoredFile:
        extension = _safe_extension(filename)
        key = f"{owner_id}/{uuid.uuid4()}{extension}"
        destination = self._resolve(key)

        try:
            # Keyword args via partial: `mkdir`'s first positional is `mode`,
            # so passing flags positionally silently creates an unwritable
            # directory instead of setting `parents`/`exist_ok`.
            await anyio.to_thread.run_sync(
                partial(destination.parent.mkdir, parents=True, exist_ok=True)
            )
            await anyio.to_thread.run_sync(destination.write_bytes, content)
        except OSError as exc:
            raise StorageError(f"Could not store the file: {exc.strerror}") from exc

        return StoredFile(
            key=key,
            size_bytes=len(content),
            content_type=content_type,
            checksum=hashlib.sha256(content).hexdigest(),
        )

    async def read(self, key: str) -> bytes:
        path = self._resolve(key)
        try:
            return await anyio.to_thread.run_sync(path.read_bytes)
        except FileNotFoundError as exc:
            raise StorageError("The stored file is missing.") from exc
        except OSError as exc:
            raise StorageError(f"Could not read the file: {exc.strerror}") from exc

    async def delete(self, key: str) -> None:
        path = self._resolve(key)
        try:
            await anyio.to_thread.run_sync(partial(path.unlink, missing_ok=True))
        except OSError as exc:
            raise StorageError(f"Could not delete the file: {exc.strerror}") from exc

    async def exists(self, key: str) -> bool:
        return await anyio.to_thread.run_sync(self._resolve(key).exists)

    def _resolve(self, key: str) -> Path:
        """Map a key to a path inside the root, or refuse.

        Two independent checks: the key must match the generated shape, and the
        resolved path must still be under the root. The second catches anything
        the first misses, including symlinks.
        """
        if not _KEY_PATTERN.match(key):
            raise StorageError("Invalid storage key.")

        candidate = (self._root / key).resolve()
        if not candidate.is_relative_to(self._root):
            raise StorageError("Invalid storage key.")
        return candidate


def _safe_extension(filename: str) -> str:
    """The file's extension if it is one we recognise, else nothing.

    Derived from the *original* name purely to keep stored files inspectable;
    it never influences where the file is written.
    """
    suffix = Path(filename).suffix.lower()
    return suffix if suffix in _SAFE_EXTENSIONS else ""
