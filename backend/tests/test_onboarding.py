"""Onboarding and the 18+ age requirement."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import calculate_age, is_adult
from app.models.user import User

ONBOARDING = "/api/auth/onboarding"
SIGNUP = "/api/auth/signup"
PASSWORD = "a-strong-passphrase"


async def _register(client: AsyncClient) -> str:
    response = await client.post(
        SIGNUP, json={"name": "Ada", "email": "ada@example.com", "password": PASSWORD}
    )
    return response.json()["access_token"]


def _birthday_years_ago(years: int, *, offset_days: int = 0) -> str:
    today = date.today()
    try:
        birthday = today.replace(year=today.year - years)
    except ValueError:  # 29 February in a non-leap target year
        birthday = today.replace(year=today.year - years, day=28)
    return (birthday + timedelta(days=offset_days)).isoformat()


async def test_onboarding_accepts_an_adult(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    token = await _register(api_client)

    response = await api_client.post(
        ONBOARDING,
        json={"date_of_birth": _birthday_years_ago(30)},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["onboarding_complete"] is True
    user = (
        await db_session.execute(select(User).where(User.email == "ada@example.com"))
    ).scalar_one()
    assert user.date_of_birth is not None


async def test_onboarding_accepts_someone_exactly_eighteen_today(
    api_client: AsyncClient,
) -> None:
    """The boundary is inclusive: the 18th birthday itself qualifies."""
    token = await _register(api_client)

    response = await api_client.post(
        ONBOARDING,
        json={"date_of_birth": _birthday_years_ago(18)},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200


async def test_onboarding_rejects_someone_one_day_short_of_eighteen(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    token = await _register(api_client)

    response = await api_client.post(
        ONBOARDING,
        json={"date_of_birth": _birthday_years_ago(18, offset_days=1)},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "age_requirement_not_met"
    # Nothing is persisted for a rejected applicant.
    user = (
        await db_session.execute(select(User).where(User.email == "ada@example.com"))
    ).scalar_one()
    assert user.date_of_birth is None


@pytest.mark.parametrize("years", [1, 10, 17], ids=["infant", "child", "seventeen"])
async def test_onboarding_rejects_minors(api_client: AsyncClient, years: int) -> None:
    token = await _register(api_client)

    response = await api_client.post(
        ONBOARDING,
        json={"date_of_birth": _birthday_years_ago(years)},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


async def test_onboarding_rejects_a_future_date_of_birth(api_client: AsyncClient) -> None:
    token = await _register(api_client)
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    response = await api_client.post(
        ONBOARDING,
        json={"date_of_birth": tomorrow},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422


async def test_onboarding_rejects_an_implausible_date_of_birth(
    api_client: AsyncClient,
) -> None:
    token = await _register(api_client)

    response = await api_client.post(
        ONBOARDING,
        json={"date_of_birth": "1850-01-01"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422


async def test_onboarding_requires_authentication(api_client: AsyncClient) -> None:
    response = await api_client.post(ONBOARDING, json={"date_of_birth": "1990-01-01"})

    assert response.status_code == 401


async def test_client_supplied_age_is_ignored(api_client: AsyncClient) -> None:
    """Age is derived from the date of birth server-side, never trusted from input."""
    token = await _register(api_client)

    response = await api_client.post(
        ONBOARDING,
        json={"date_of_birth": _birthday_years_ago(12), "age": 42, "onboarding_complete": True},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


# ------------------------------------------------------- pure age arithmetic


@pytest.mark.parametrize(
    ("born", "today", "expected"),
    [
        (date(2000, 1, 1), date(2026, 1, 1), 26),
        (date(2000, 1, 2), date(2026, 1, 1), 25),
        (date(2008, 8, 20), date(2026, 8, 20), 18),
        (date(2008, 8, 21), date(2026, 8, 20), 17),
        # A 29 February birthday counts on 1 March in non-leap years.
        (date(2000, 2, 29), date(2026, 2, 28), 25),
        (date(2000, 2, 29), date(2026, 3, 1), 26),
        (date(2000, 2, 29), date(2024, 2, 29), 24),
    ],
    ids=[
        "birthday-today",
        "day-before-birthday",
        "eighteen-exactly",
        "one-day-short",
        "leap-birthday-feb-28",
        "leap-birthday-mar-1",
        "leap-birthday-on-leap-day",
    ],
)
def test_calculate_age(born: date, today: date, expected: int) -> None:
    assert calculate_age(born, today=today) == expected


def test_is_adult_boundary() -> None:
    assert is_adult(date(2008, 8, 20), today=date(2026, 8, 20)) is True
    assert is_adult(date(2008, 8, 21), today=date(2026, 8, 20)) is False
