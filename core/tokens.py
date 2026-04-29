import os
import uuid
import jwt
from datetime import datetime, timezone, timedelta
from django.conf import settings


def _secret():
    return settings.SECRET_KEY


def generate_access_token(user) -> str:
    """Creates a short-lived signed JWT access token."""
    expiry = datetime.now(timezone.utc) + timedelta(
        seconds=settings.ACCESS_TOKEN_EXPIRY_SECONDS
    )
    payload = {
        "sub": str(user.id),
        "github_id": user.github_id,
        "username": user.username,
        "role": user.role,
        "exp": expiry,
        "iat": datetime.now(timezone.utc),
        "type": "access",
    }
    return jwt.encode(payload, _secret(), algorithm="HS256")


def generate_refresh_token() -> str:
    """Creates an opaque refresh token (UUID4)."""
    return str(uuid.uuid4())


def decode_access_token(token: str) -> dict:
    """
    Decodes and validates access token.
    Raises jwt.ExpiredSignatureError or jwt.InvalidTokenError on failure.
    """
    return jwt.decode(token, _secret(), algorithms=["HS256"])


def issue_token_pair(user, RefreshToken) -> dict:
    """
    Issues a new access + refresh token pair.
    Invalidates all previous refresh tokens for the user.
    """
    # Revoke existing tokens
    RefreshToken.objects.filter(user=user, revoked=False).update(revoked=True)

    access = generate_access_token(user)
    refresh_value = generate_refresh_token()

    expires_at = datetime.now(timezone.utc) + timedelta(
        seconds=settings.REFRESH_TOKEN_EXPIRY_SECONDS
    )
    RefreshToken.objects.create(
        user=user,
        token=refresh_value,
        expires_at=expires_at,
    )

    return {
        "access_token": access,
        "refresh_token": refresh_value,
    }
