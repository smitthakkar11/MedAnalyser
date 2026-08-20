"""Local file storage.

The storage layer holds uploaded medical documents, so the property that
matters most is that no key — however hostile or corrupted — can read or write
outside the storage root.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import Settings
from app.services.storage import LocalStorageProvider, StorageError, StorageService
from app.services.storage.factory import build_storage_service

OWNER = "11111111-1111-1111-1111-111111111111"
OTHER = "22222222-2222-2222-2222-222222222222"


@pytest.fixture
def storage(tmp_path: Path) -> LocalStorageProvider:
    return LocalStorageProvider(tmp_path / "storage")


async def test_saving_returns_a_handle(storage: LocalStorageProvider) -> None:
    stored = await storage.save(
        owner_id=OWNER, filename="cbc.pdf", content=b"%PDF-1.4", content_type="application/pdf"
    )

    assert stored.key.startswith(f"{OWNER}/")
    assert stored.size_bytes == 8
    assert len(stored.checksum) == 64


async def test_a_round_trip_preserves_the_bytes(storage: LocalStorageProvider) -> None:
    content = b"%PDF-1.4\nbinary\x00\xff bytes"

    stored = await storage.save(
        owner_id=OWNER, filename="r.pdf", content=content, content_type="application/pdf"
    )

    assert await storage.read(stored.key) == content


async def test_the_stored_name_is_generated_not_the_users(
    storage: LocalStorageProvider,
) -> None:
    """An uploaded filename is attacker-controlled and never becomes a path."""
    stored = await storage.save(
        owner_id=OWNER,
        filename="../../../etc/passwd.pdf",
        content=b"%PDF-",
        content_type="application/pdf",
    )

    assert ".." not in stored.key
    assert "etc" not in stored.key
    assert (storage.root / stored.key).is_relative_to(storage.root)


async def test_files_are_namespaced_by_owner(storage: LocalStorageProvider) -> None:
    mine = await storage.save(
        owner_id=OWNER, filename="a.pdf", content=b"a", content_type="application/pdf"
    )
    theirs = await storage.save(
        owner_id=OTHER, filename="a.pdf", content=b"b", content_type="application/pdf"
    )

    assert mine.key.split("/")[0] != theirs.key.split("/")[0]


async def test_identical_content_gives_an_identical_checksum(
    storage: LocalStorageProvider,
) -> None:
    """Duplicate detection depends on this."""
    first = await storage.save(
        owner_id=OWNER, filename="a.pdf", content=b"same", content_type="application/pdf"
    )
    second = await storage.save(
        owner_id=OWNER, filename="b.pdf", content=b"same", content_type="application/pdf"
    )

    assert first.checksum == second.checksum
    assert first.key != second.key


@pytest.mark.parametrize(
    "key",
    [
        "../escape",
        "../../etc/passwd",
        "/etc/passwd",
        "a/b/c",
        f"{OWNER}/../../../etc/passwd",
        f"{OWNER}/../{OTHER}/file.pdf",
        "",
        f"{OWNER}/not-a-uuid.pdf",
    ],
)
async def test_traversal_and_malformed_keys_are_refused(
    storage: LocalStorageProvider, key: str
) -> None:
    """Re-validated on read, so even a corrupted database row cannot escape."""
    with pytest.raises(StorageError):
        await storage.read(key)


async def test_reading_a_missing_file_reports_clearly(
    storage: LocalStorageProvider,
) -> None:
    missing = f"{OWNER}/33333333-3333-3333-3333-333333333333.pdf"

    with pytest.raises(StorageError, match="missing"):
        await storage.read(missing)


async def test_deleting_is_idempotent(storage: LocalStorageProvider) -> None:
    """Cleanup must not fail because a file is already gone."""
    stored = await storage.save(
        owner_id=OWNER, filename="a.pdf", content=b"a", content_type="application/pdf"
    )

    await storage.delete(stored.key)
    await storage.delete(stored.key)

    assert await storage.exists(stored.key) is False


async def test_saving_creates_a_writable_directory(tmp_path: Path) -> None:
    """Regression: `mkdir(True, True)` sets mode=1 positionally, producing a
    directory with no write permission rather than `parents=True`."""
    storage = LocalStorageProvider(tmp_path / "nested" / "deeper" / "storage")

    stored = await storage.save(
        owner_id=OWNER, filename="a.pdf", content=b"a", content_type="application/pdf"
    )

    assert await storage.read(stored.key) == b"a"


def test_the_factory_builds_the_configured_provider(tmp_path: Path) -> None:
    settings = Settings(
        storage_provider="local",
        file_storage_path=tmp_path,
        _env_file=None,  # type: ignore[call-arg]
    )

    service = build_storage_service(settings)

    assert isinstance(service, LocalStorageProvider)
    assert isinstance(service, StorageService)


def test_an_unknown_provider_fails_loudly(tmp_path: Path) -> None:
    settings = Settings(
        storage_provider="s3",
        file_storage_path=tmp_path,
        _env_file=None,  # type: ignore[call-arg]
    )

    with pytest.raises(ValueError, match="Unknown STORAGE_PROVIDER"):
        build_storage_service(settings)
