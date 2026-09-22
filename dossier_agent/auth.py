"""Small dependency-light password and signed-session-token helpers."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from dataclasses import dataclass


PASSWORD_ITERATIONS = 310_000
TOKEN_TTL_SECONDS = 60 * 60 * 24 * 7


class AuthenticationError(ValueError):
    """Raised when credentials or a session token are invalid."""


@dataclass(frozen=True)
class AuthIdentity:
    user_id: int
    email: str


def _secret() -> bytes:
    return os.getenv("DOSSIER_AUTH_SECRET", "dev-only-change-me").encode("utf-8")


def normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if "@" not in normalized or len(normalized) > 320:
        raise AuthenticationError("Enter a valid email address.")
    return normalized


def hash_password(password: str) -> str:
    if len(password) < 8:
        raise AuthenticationError("Password must be at least 8 characters.")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS
    )
    encoded_salt = base64.urlsafe_b64encode(salt).decode("ascii")
    encoded_digest = base64.urlsafe_b64encode(digest).decode("ascii")
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${encoded_salt}${encoded_digest}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt_value, digest_value = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.urlsafe_b64decode(salt_value.encode("ascii"))
        expected = base64.urlsafe_b64decode(digest_value.encode("ascii"))
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, int(iterations)
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def issue_token(identity: AuthIdentity) -> str:
    payload = {
        "sub": identity.user_id,
        "email": identity.email,
        "exp": int(time.time()) + TOKEN_TTL_SECONDS,
    }
    encoded_payload = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    ).decode("ascii").rstrip("=")
    signature = hmac.new(_secret(), encoded_payload.encode("ascii"), hashlib.sha256).digest()
    encoded_signature = base64.urlsafe_b64encode(signature).decode("ascii").rstrip("=")
    return f"{encoded_payload}.{encoded_signature}"


def read_token(token: str) -> AuthIdentity:
    try:
        encoded_payload, encoded_signature = token.split(".", 1)
        expected_signature = hmac.new(
            _secret(), encoded_payload.encode("ascii"), hashlib.sha256
        ).digest()
        supplied_signature = base64.urlsafe_b64decode(
            encoded_signature + "=" * (-len(encoded_signature) % 4)
        )
        if not hmac.compare_digest(expected_signature, supplied_signature):
            raise AuthenticationError("Invalid session token.")
        payload = json.loads(
            base64.urlsafe_b64decode(encoded_payload + "=" * (-len(encoded_payload) % 4))
        )
        if int(payload["exp"]) <= int(time.time()):
            raise AuthenticationError("Session token has expired.")
        return AuthIdentity(user_id=int(payload["sub"]), email=normalize_email(payload["email"]))
    except (KeyError, TypeError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
        raise AuthenticationError("Invalid session token.") from exc
