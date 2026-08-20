"""User medical profile: reading, replacing, validation and ownership."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.profile import Allergy, Condition, Medication

PROFILE = "/api/profile"
SIGNUP = "/api/auth/signup"
PASSWORD = "a-strong-passphrase"


async def _onboarded(client: AsyncClient, email: str = "ada@example.com") -> str:
    """Register, complete onboarding, and return an access token."""
    signup = await client.post(
        SIGNUP, json={"name": "Ada Lovelace", "email": email, "password": PASSWORD}
    )
    assert signup.status_code == 201
    token = signup.json()["access_token"]
    onboarding = await client.post(
        "/api/auth/onboarding",
        json={"date_of_birth": "1990-05-04"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert onboarding.status_code == 200
    return token


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ------------------------------------------------------------------ reading


async def test_profile_is_created_empty_on_first_read(api_client: AsyncClient) -> None:
    token = await _onboarded(api_client)

    response = await api_client.get(PROFILE, headers=_auth(token))

    assert response.status_code == 200
    body = response.json()
    assert body["allergies"] == []
    assert body["conditions"] == []
    assert body["medications"] == []
    assert body["sex_at_birth"] is None
    assert body["completeness"] == 0


async def test_profile_exposes_age_derived_from_date_of_birth(
    api_client: AsyncClient,
) -> None:
    """Age is computed server-side, not stored or supplied by the client."""
    token = await _onboarded(api_client)

    body = (await api_client.get(PROFILE, headers=_auth(token))).json()

    assert body["date_of_birth"] == "1990-05-04"
    # Built from UTC, because the service derives age from the server clock.
    today = datetime.now(UTC).date()
    expected = today.year - 1990 - ((today.month, today.day) < (5, 4))
    assert body["age"] == expected


async def test_reading_the_profile_twice_does_not_create_two_rows(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    from app.models.profile import UserProfile

    token = await _onboarded(api_client)

    await api_client.get(PROFILE, headers=_auth(token))
    await api_client.get(PROFILE, headers=_auth(token))

    assert await db_session.scalar(select(func.count()).select_from(UserProfile)) == 1


# ------------------------------------------------------------------ writing


async def test_profile_can_be_populated(api_client: AsyncClient) -> None:
    token = await _onboarded(api_client)

    response = await api_client.put(
        PROFILE,
        headers=_auth(token),
        json={
            "sex_at_birth": "female",
            "gender_identity": "Woman",
            "emergency_contact_name": "Grace Hopper",
            "emergency_contact_relationship": "Sister",
            "emergency_contact_phone": "+44 20 7946 0000",
            "allergies": [{"substance": "Penicillin", "reaction": "Hives", "severity": "severe"}],
            "conditions": [{"name": "Asthma", "status": "managed", "diagnosed_year": 2005}],
            "medications": [
                {
                    "name": "Salbutamol",
                    "dosage": "100 mcg",
                    "frequency": "As needed",
                    "is_current": True,
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["sex_at_birth"] == "female"
    assert body["gender_identity"] == "Woman"
    assert body["allergies"][0]["substance"] == "Penicillin"
    assert body["allergies"][0]["severity"] == "severe"
    assert body["conditions"][0]["diagnosed_year"] == 2005
    assert body["medications"][0]["dosage"] == "100 mcg"
    assert body["completeness"] == 100


async def test_profile_changes_persist_across_requests(api_client: AsyncClient) -> None:
    token = await _onboarded(api_client)
    await api_client.put(
        PROFILE,
        headers=_auth(token),
        json={"sex_at_birth": "male", "allergies": [{"substance": "Latex"}]},
    )

    body = (await api_client.get(PROFILE, headers=_auth(token))).json()

    assert body["sex_at_birth"] == "male"
    assert [item["substance"] for item in body["allergies"]] == ["Latex"]


async def test_collections_are_replaced_not_appended(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """A save replaces the collection; stale rows must not linger."""
    token = await _onboarded(api_client)
    await api_client.put(
        PROFILE,
        headers=_auth(token),
        json={"allergies": [{"substance": "Latex"}, {"substance": "Pollen"}]},
    )

    response = await api_client.put(
        PROFILE, headers=_auth(token), json={"allergies": [{"substance": "Pollen"}]}
    )

    assert [item["substance"] for item in response.json()["allergies"]] == ["Pollen"]
    assert await db_session.scalar(select(func.count()).select_from(Allergy)) == 1


async def test_clearing_every_collection_leaves_no_rows(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    token = await _onboarded(api_client)
    await api_client.put(
        PROFILE,
        headers=_auth(token),
        json={
            "allergies": [{"substance": "Latex"}],
            "conditions": [{"name": "Asthma"}],
            "medications": [{"name": "Salbutamol"}],
        },
    )

    response = await api_client.put(PROFILE, headers=_auth(token), json={})

    assert response.status_code == 200
    for model in (Allergy, Condition, Medication):
        assert await db_session.scalar(select(func.count()).select_from(model)) == 0


async def test_blank_strings_are_stored_as_absent(api_client: AsyncClient) -> None:
    """An empty form field means "not answered", not an empty string."""
    token = await _onboarded(api_client)

    response = await api_client.put(
        PROFILE,
        headers=_auth(token),
        json={"gender_identity": "   ", "emergency_contact_name": ""},
    )

    assert response.json()["gender_identity"] is None
    assert response.json()["emergency_contact_name"] is None


async def test_medications_list_current_first(api_client: AsyncClient) -> None:
    token = await _onboarded(api_client)

    response = await api_client.put(
        PROFILE,
        headers=_auth(token),
        json={
            "medications": [
                {"name": "Amoxicillin", "is_current": False},
                {"name": "Salbutamol", "is_current": True},
            ]
        },
    )

    assert [m["name"] for m in response.json()["medications"]] == [
        "Salbutamol",
        "Amoxicillin",
    ]


# --------------------------------------------------------------- validation


@pytest.mark.parametrize(
    ("payload", "reason"),
    [
        ({"allergies": [{"substance": ""}]}, "blank substance"),
        ({"conditions": [{"name": ""}]}, "blank condition name"),
        ({"medications": [{"name": ""}]}, "blank medication name"),
        ({"sex_at_birth": "not-an-option"}, "invalid enum"),
        ({"conditions": [{"name": "X", "status": "made-up"}]}, "invalid status"),
        ({"conditions": [{"name": "X", "diagnosed_year": 1500}]}, "year too early"),
    ],
)
async def test_invalid_profile_payloads_are_rejected(
    api_client: AsyncClient, payload: dict, reason: str
) -> None:
    token = await _onboarded(api_client)

    response = await api_client.put(PROFILE, headers=_auth(token), json=payload)

    assert response.status_code == 422, reason


async def test_future_dates_are_rejected(api_client: AsyncClient) -> None:
    token = await _onboarded(api_client)
    tomorrow = (datetime.now(UTC).date() + timedelta(days=1)).isoformat()

    future_start = await api_client.put(
        PROFILE,
        headers=_auth(token),
        json={"medications": [{"name": "X", "started_on": tomorrow}]},
    )
    future_year = await api_client.put(
        PROFILE,
        headers=_auth(token),
        json={"conditions": [{"name": "X", "diagnosed_year": datetime.now(UTC).year + 1}]},
    )

    assert future_start.status_code == 422
    assert future_year.status_code == 422


async def test_oversized_collections_are_rejected(api_client: AsyncClient) -> None:
    """A single request must not be able to write unbounded rows."""
    token = await _onboarded(api_client)

    response = await api_client.put(
        PROFILE,
        headers=_auth(token),
        json={"allergies": [{"substance": f"Substance {i}"} for i in range(101)]},
    )

    assert response.status_code == 422


# ---------------------------------------------------------------- ownership


async def test_profile_requires_authentication(api_client: AsyncClient) -> None:
    assert (await api_client.get(PROFILE)).status_code == 401
    assert (await api_client.put(PROFILE, json={})).status_code == 401


async def test_profile_requires_completed_onboarding(api_client: AsyncClient) -> None:
    """An account that has not passed the age check cannot hold medical data."""
    signup = await api_client.post(
        SIGNUP, json={"name": "Ada", "email": "ada@example.com", "password": PASSWORD}
    )
    token = signup.json()["access_token"]

    response = await api_client.get(PROFILE, headers=_auth(token))

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "onboarding_required"


async def test_one_user_cannot_see_anothers_profile(api_client: AsyncClient) -> None:
    """The core guarantee: no token reaches another user's medical data."""
    ada = await _onboarded(api_client, "ada@example.com")
    grace = await _onboarded(api_client, "grace@example.com")

    await api_client.put(
        PROFILE,
        headers=_auth(ada),
        json={
            "allergies": [{"substance": "Penicillin"}],
            "conditions": [{"name": "Asthma"}],
            "notes": "Ada's private note",
        },
    )

    graces_view = await api_client.get(PROFILE, headers=_auth(grace))

    assert graces_view.status_code == 200
    assert graces_view.json()["allergies"] == []
    assert graces_view.json()["conditions"] == []
    assert graces_view.json()["notes"] is None


async def test_one_user_cannot_overwrite_anothers_collections(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Replacement is scoped by user id, so a save cannot delete another's rows."""
    ada = await _onboarded(api_client, "ada@example.com")
    grace = await _onboarded(api_client, "grace@example.com")
    await api_client.put(
        PROFILE, headers=_auth(ada), json={"allergies": [{"substance": "Penicillin"}]}
    )

    # Grace saves an empty profile — a full replacement of *her* collections.
    await api_client.put(PROFILE, headers=_auth(grace), json={"allergies": []})

    adas_view = await api_client.get(PROFILE, headers=_auth(ada))
    assert [item["substance"] for item in adas_view.json()["allergies"]] == ["Penicillin"]
    assert await db_session.scalar(select(func.count()).select_from(Allergy)) == 1


async def test_deleting_a_user_removes_their_medical_data(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    """Cascade rules must leave no orphaned medical rows behind."""
    from app.models.user import User

    token = await _onboarded(api_client)
    await api_client.put(
        PROFILE,
        headers=_auth(token),
        json={
            "allergies": [{"substance": "Latex"}],
            "conditions": [{"name": "Asthma"}],
            "medications": [{"name": "Salbutamol"}],
        },
    )

    user = (await db_session.execute(select(User))).scalars().first()
    assert user is not None
    await db_session.delete(user)
    await db_session.commit()

    for model in (Allergy, Condition, Medication):
        assert await db_session.scalar(select(func.count()).select_from(model)) == 0


async def test_a_blank_put_erases_the_profile(api_client: AsyncClient) -> None:
    """PUT replaces the whole document — including with nothing.

    This is the intended contract, and it is exactly why any client that offers
    a "save" must first load the existing profile into its draft. The onboarding
    wizard learned this the hard way: resuming it with an empty draft and
    saving destroyed the user's records.
    """
    token = await _onboarded(api_client)
    await api_client.put(
        PROFILE,
        headers=_auth(token),
        json={
            "sex_at_birth": "male",
            "conditions": [{"name": "Type 2 diabetes"}],
            "medications": [{"name": "Metformin"}],
        },
    )

    response = await api_client.put(PROFILE, headers=_auth(token), json={})

    assert response.status_code == 200
    assert response.json()["sex_at_birth"] is None
    assert response.json()["conditions"] == []
    assert response.json()["medications"] == []


async def test_a_round_trip_through_get_then_put_preserves_everything(
    api_client: AsyncClient,
) -> None:
    """The safe client pattern: GET, edit, PUT back.

    Guards the onboarding/profile contract — whatever `GET` returns must be
    accepted by `PUT` and leave the profile unchanged. If a field ever stops
    round-tripping (returned by `GET` but dropped on write), this fails.
    """
    token = await _onboarded(api_client)
    original = {
        "sex_at_birth": "female",
        "gender_identity": "Woman",
        "notes": "Non-smoker.",
        "emergency_contact_name": "Grace Hopper",
        "emergency_contact_relationship": "Sister",
        "emergency_contact_phone": "+44 20 7946 0000",
        "allergies": [{"substance": "Penicillin", "reaction": "Hives", "severity": "severe"}],
        "conditions": [{"name": "Asthma", "status": "managed", "diagnosed_year": 2005}],
        "medications": [{"name": "Salbutamol", "dosage": "100 mcg", "frequency": "As needed"}],
    }
    await api_client.put(PROFILE, headers=_auth(token), json=original)

    fetched = (await api_client.get(PROFILE, headers=_auth(token))).json()
    # Send back exactly what was read, minus the response-only fields.
    for response_only in ("date_of_birth", "age", "completeness"):
        fetched.pop(response_only)
    replayed = await api_client.put(PROFILE, headers=_auth(token), json=fetched)

    assert replayed.status_code == 200
    body = replayed.json()
    assert body["sex_at_birth"] == "female"
    assert body["gender_identity"] == "Woman"
    assert [a["substance"] for a in body["allergies"]] == ["Penicillin"]
    assert [c["name"] for c in body["conditions"]] == ["Asthma"]
    assert [m["name"] for m in body["medications"]] == ["Salbutamol"]
    assert body["completeness"] == 100
