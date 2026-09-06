"""
Password reset token utilities.

Raw tokens are 32-byte URL-safe strings generated with ``secrets``.
Only their HMAC-SHA256 hexdigest is persisted to the database — the raw
token is never stored.
"""

import hashlib
import hmac
import secrets

from django.conf import settings
from django.utils import timezone

from .models import PasswordResetToken, User


def _hash_token(raw_token: str) -> str:
    """Return the HMAC-SHA256 hex digest of *raw_token* keyed with SECRET_KEY."""
    key = settings.SECRET_KEY.encode()
    return hmac.new(key, raw_token.encode(), hashlib.sha256).hexdigest()


def generate_password_reset_token(user: User) -> tuple[str, PasswordResetToken]:
    """
    Create a new PasswordResetToken for *user* and return
    ``(raw_token, token_instance)``.

    The caller is responsible for embedding *raw_token* in the reset URL
    sent to the user.  Only the hash is stored in the DB.
    """
    timeout_seconds: int = getattr(settings, "PASSWORD_RESET_TIMEOUT", 3600)

    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw_token)
    expires_at = timezone.now() + timezone.timedelta(seconds=timeout_seconds)

    # Invalidate any previous unused tokens for this user
    PasswordResetToken.objects.filter(user=user, used=False).update(used=True)

    token_instance = PasswordResetToken.objects.create(
        user=user,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    return raw_token, token_instance


def verify_password_reset_token(raw_token: str) -> PasswordResetToken | None:
    """
    Validate *raw_token* and return the corresponding ``PasswordResetToken``
    if it is valid (exists, not used, not expired).

    Returns ``None`` if the token is invalid for any reason.
    """
    token_hash = _hash_token(raw_token)
    try:
        token_instance = PasswordResetToken.objects.select_related("user").get(
            token_hash=token_hash
        )
    except PasswordResetToken.DoesNotExist:
        return None

    if not token_instance.is_valid:
        return None

    return token_instance
