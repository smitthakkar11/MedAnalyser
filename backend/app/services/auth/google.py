"""Google identity verification.

The browser obtains an OpenID Connect ID token from Google and posts it here.
The token is verified **server-side** against Google's published JWKS: signature,
issuer, audience (our client id) and expiry are all checked. Nothing the client
claims about its own identity is trusted.

Verification sits behind a Protocol so tests — and any future provider — can
substitute an implementation without touching the auth service.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol, runtime_checkable

import anyio
import jwt
from jwt import PyJWKClient
from pydantic import BaseModel

from app.core.config import Settings

logger = logging.getLogger(__name__)

#: Google's JWKS endpoint and the issuers it signs tokens as.
GOOGLE_JWKS_URI = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = ("https://accounts.google.com", "accounts.google.com")
GOOGLE_PROVIDER = "google"


class GoogleVerificationError(Exception):
    """Raised when a Google ID token cannot be verified."""


class GoogleIdentity(BaseModel):
    """A verified Google identity.

    ``subject`` is Google's stable ``sub`` claim — the only identifier safe to
    key an account on, since a user's email address at Google can change.
    """

    subject: str
    email: str
    email_verified: bool
    name: str | None = None


@runtime_checkable
class GoogleTokenVerifier(Protocol):
    """Verifies a Google ID token and returns the identity it asserts."""

    async def verify(self, id_token: str) -> GoogleIdentity:
        """Raises GoogleVerificationError if the token is not valid."""
        ...


class GoogleJwksVerifier:
    """Verifies ID tokens against Google's published signing keys."""

    def __init__(self, client_id: str, *, jwks_uri: str = GOOGLE_JWKS_URI) -> None:
        if not client_id:
            raise ValueError("A Google client id is required to verify ID tokens.")
        self._client_id = client_id
        # PyJWKClient caches keys and refreshes them when an unknown kid appears.
        self._jwk_client = PyJWKClient(jwks_uri, cache_keys=True)

    def _verify_sync(self, id_token: str) -> GoogleIdentity:
        try:
            signing_key = self._jwk_client.get_signing_key_from_jwt(id_token)
            claims: dict[str, Any] = jwt.decode(
                id_token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self._client_id,
                issuer=list(GOOGLE_ISSUERS),
                options={"require": ["exp", "iat", "sub", "aud", "iss"]},
            )
        except jwt.PyJWTError as exc:
            # The reason is logged for operators but never returned to the client.
            logger.warning("Google ID token rejected", extra={"reason": type(exc).__name__})
            raise GoogleVerificationError("Google sign-in could not be verified.") from exc
        except Exception as exc:  # noqa: BLE001 - network/JWKS failures
            logger.warning("Google JWKS lookup failed", extra={"reason": type(exc).__name__})
            raise GoogleVerificationError("Google sign-in is temporarily unavailable.") from exc

        email = claims.get("email")
        if not email:
            raise GoogleVerificationError("Google did not provide an email address.")

        return GoogleIdentity(
            subject=str(claims["sub"]),
            email=str(email).strip().lower(),
            email_verified=bool(claims.get("email_verified", False)),
            name=claims.get("name"),
        )

    async def verify(self, id_token: str) -> GoogleIdentity:
        # PyJWKClient performs blocking network I/O; keep it off the event loop.
        return await anyio.to_thread.run_sync(self._verify_sync, id_token)


def build_google_verifier(settings: Settings) -> GoogleTokenVerifier | None:
    """Return a verifier, or None when Google sign-in is not configured.

    Returning None rather than raising lets the application run without Google
    credentials; the route reports the feature as unavailable.
    """
    if not settings.google_client_id:
        return None
    return GoogleJwksVerifier(settings.google_client_id)
