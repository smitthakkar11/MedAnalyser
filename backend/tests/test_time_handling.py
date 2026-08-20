"""Date and time handling.

MedAnalyser makes date-sensitive decisions — most importantly the 18+ age gate —
from the **server's UTC clock**, never from anything the client sends. Mixing a
naive local clock into that path creates a window each day where two parts of
the same request disagree: on a machine at UTC+5:30, a user turning 18 was told
they were 17 for the first five and a half hours of their birthday.

These tests pin that contract.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from app.core.security import calculate_age, is_adult

APP_DIR = Path(__file__).resolve().parents[1] / "app"

#: `datetime.now()` and `date.today()` with no timezone read the machine's local
#: clock, which is not the clock the rest of the application uses.
_NAIVE_CLOCK = re.compile(r"datetime\.now\(\s*\)|date\.today\(\s*\)")


def test_no_application_code_reads_the_local_clock() -> None:
    """Every date decision must come from one clock.

    A source check rather than a behavioural one because the failure is
    time-of-day dependent: a behavioural test would pass in CI running at UTC
    and fail only on a developer's machine, hours after it was introduced.
    """
    offenders: list[str] = []
    for path in APP_DIR.rglob("*.py"):
        for number, line in enumerate(path.read_text().splitlines(), start=1):
            if _NAIVE_CLOCK.search(line):
                offenders.append(f"{path.relative_to(APP_DIR)}:{number}: {line.strip()}")

    assert offenders == [], (
        "Use datetime.now(UTC) instead of the machine's local clock:\n" + "\n".join(offenders)
    )


def test_age_is_computed_from_utc() -> None:
    """The documented behaviour, stated explicitly."""
    today_utc = datetime.now(UTC).date()
    eighteenth_birthday_today = today_utc.replace(year=today_utc.year - 18)

    assert is_adult(eighteenth_birthday_today) is True
    assert is_adult(eighteenth_birthday_today + timedelta(days=1)) is False


@pytest.mark.parametrize(
    ("born", "today", "expected"),
    [
        # The boundary either side of midnight UTC.
        (date(2008, 8, 21), date(2026, 8, 20), 17),
        (date(2008, 8, 21), date(2026, 8, 21), 18),
    ],
)
def test_the_age_boundary_is_exact(born: date, today: date, expected: int) -> None:
    assert calculate_age(born, today=today) == expected
