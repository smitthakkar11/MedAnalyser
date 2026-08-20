"""Download and verify the raw dataset.

Run once before training::

    python -m ml.ingest

The dataset is *not* committed: it belongs to its authors under CC BY-SA 4.0
and is trivial to re-fetch. This script is the reproducible record of exactly
what was used, including checksums of each file.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import ssl
import sys
import urllib.request
import zipfile
from pathlib import Path

from ml.config import RAW_DIR

DATASET_SLUG = "itachi9604/disease-symptom-description-dataset"
DOWNLOAD_URL = f"https://www.kaggle.com/api/v1/datasets/download/{DATASET_SLUG}"

#: Checksums are *recorded* at ingestion into `data/raw/checksums.json` and
#: reproduced in the dataset card, rather than hard-coded here. Upstream is a
#: third-party host: pinning a hash in code would turn any legitimate update
#: into an import error, while the recorded file still proves which bytes the
#: committed evaluation report was produced from.
EXPECTED_FILES = (
    "dataset.csv",
    "Symptom-severity.csv",
    "symptom_Description.csv",
    "symptom_precaution.csv",
)


def _ssl_context() -> ssl.SSLContext:
    """A verifying SSL context.

    Some Python builds (notably the python.org macOS installers) ship without a
    CA bundle, which makes `urlopen` fail on any HTTPS URL. Fall back to
    certifi's bundle rather than disabling verification.
    """
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def download(destination: Path = RAW_DIR, *, force: bool = False) -> dict[str, str]:
    """Fetch and extract the dataset, returning a checksum per file."""
    if not force and all((destination / name).exists() for name in EXPECTED_FILES):
        print(f"Dataset already present in {destination} (use --force to re-download).")
    else:
        print(f"Downloading {DATASET_SLUG} ...")
        context = _ssl_context()
        with urllib.request.urlopen(  # noqa: S310 - fixed, https-only URL
            DOWNLOAD_URL, timeout=120, context=context
        ) as response:
            payload = response.read()
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            members = set(archive.namelist())
            missing = set(EXPECTED_FILES) - members
            if missing:
                raise RuntimeError(f"Archive is missing expected files: {sorted(missing)}")
            archive.extractall(destination)
        print(f"Extracted {len(EXPECTED_FILES)} files to {destination}")

    checksums = {name: sha256_of(destination / name) for name in EXPECTED_FILES}
    (destination / "checksums.json").write_text(json.dumps(checksums, indent=2) + "\n")
    for name, digest in checksums.items():
        print(f"  {name:<28} {digest[:16]}…")
    return checksums


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Re-download even if present.")
    args = parser.parse_args()
    try:
        download(force=args.force)
    except Exception as exc:  # noqa: BLE001 - a CLI should report, not traceback
        print(f"Ingestion failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
