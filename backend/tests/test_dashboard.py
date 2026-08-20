"""Dashboard summary."""

from __future__ import annotations

from httpx import AsyncClient

DASHBOARD = "/api/dashboard"
PROFILE = "/api/profile"
SIGNUP = "/api/auth/signup"
PASSWORD = "a-strong-passphrase"


async def _onboarded(client: AsyncClient, email: str = "ada@example.com") -> str:
    signup = await client.post(
        SIGNUP, json={"name": "Ada Lovelace", "email": email, "password": PASSWORD}
    )
    token = signup.json()["access_token"]
    await client.post(
        "/api/auth/onboarding",
        json={"date_of_birth": "1990-05-04"},
        headers={"Authorization": f"Bearer {token}"},
    )
    return token


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_dashboard_for_a_new_account(api_client: AsyncClient) -> None:
    token = await _onboarded(api_client)

    response = await api_client.get(DASHBOARD, headers=_auth(token))

    assert response.status_code == 200
    body = response.json()
    assert body["user_name"] == "Ada Lovelace"
    assert body["profile"]["completeness"] == 0
    assert body["profile"]["allergy_count"] == 0
    # Present and zero rather than absent, so the contract survives Phases 4/5.
    assert body["assessment_count"] == 0
    assert body["report_count"] == 0


async def test_dashboard_reflects_the_profile(api_client: AsyncClient) -> None:
    token = await _onboarded(api_client)
    await api_client.put(
        PROFILE,
        headers=_auth(token),
        json={
            "sex_at_birth": "female",
            "allergies": [{"substance": "Penicillin"}, {"substance": "Latex"}],
            "conditions": [{"name": "Asthma"}],
            "medications": [
                {"name": "Salbutamol", "is_current": True},
                {"name": "Amoxicillin", "is_current": False},
            ],
        },
    )

    body = (await api_client.get(DASHBOARD, headers=_auth(token))).json()

    assert body["profile"]["allergy_count"] == 2
    assert body["profile"]["condition_count"] == 1
    # Only medications the user still takes are counted.
    assert body["profile"]["current_medication_count"] == 1
    assert body["profile"]["completeness"] > 0


async def test_dashboard_requires_authentication(api_client: AsyncClient) -> None:
    assert (await api_client.get(DASHBOARD)).status_code == 401


async def test_dashboard_requires_completed_onboarding(api_client: AsyncClient) -> None:
    signup = await api_client.post(
        SIGNUP, json={"name": "Ada", "email": "ada@example.com", "password": PASSWORD}
    )

    response = await api_client.get(DASHBOARD, headers=_auth(signup.json()["access_token"]))

    assert response.status_code == 403


async def test_dashboard_shows_only_the_signed_in_users_data(
    api_client: AsyncClient,
) -> None:
    ada = await _onboarded(api_client, "ada@example.com")
    grace = await _onboarded(api_client, "grace@example.com")
    await api_client.put(
        PROFILE, headers=_auth(ada), json={"allergies": [{"substance": "Penicillin"}]}
    )

    body = (await api_client.get(DASHBOARD, headers=_auth(grace))).json()

    assert body["user_name"] == "Ada Lovelace"  # both fixtures use the same name
    assert body["profile"]["allergy_count"] == 0
