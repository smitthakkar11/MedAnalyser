"""Test doubles for external dependencies."""

from __future__ import annotations

from app.services.auth.google import GoogleIdentity, GoogleVerificationError


class FakeGoogleVerifier:
    """A Google verifier that resolves pre-registered tokens.

    Substituting this for the real verifier keeps the test suite off the network
    while still exercising every branch of the sign-in and linking logic. Any
    token that has not been registered is rejected, exactly as an invalid token
    would be.
    """

    def __init__(self) -> None:
        self._identities: dict[str, GoogleIdentity] = {}

    def register(
        self,
        id_token: str,
        *,
        subject: str,
        email: str,
        email_verified: bool = True,
        name: str | None = None,
    ) -> GoogleIdentity:
        """Make *id_token* resolve to the given identity."""
        identity = GoogleIdentity(
            subject=subject,
            email=email.strip().lower(),
            email_verified=email_verified,
            name=name,
        )
        self._identities[id_token] = identity
        return identity

    async def verify(self, id_token: str) -> GoogleIdentity:
        try:
            return self._identities[id_token]
        except KeyError as exc:
            raise GoogleVerificationError("Google sign-in could not be verified.") from exc
