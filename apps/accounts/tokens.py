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


from datetime import timedelta
from rest_framework_simplejwt.tokens import Token
from .models import OTP, OTPPurpose


class OTPSessionToken(Token):
    """
    Short-lived signed JWT issued upon valid password authentication
    when 2FA is enabled. Used solely to complete the OTP verification step.
    """
    token_type = "otp_session"
    lifetime = timedelta(seconds=getattr(settings, "OTP_EXPIRY_SECONDS", 600))


def generate_otp(user: User, purpose: str = OTPPurpose.LOGIN) -> tuple[str, OTP]:
    """
    Create a new 6-digit OTP for *user* and *purpose*.
    Invalidates any previous unused OTPs for the same user and purpose.
    Returns ``(raw_code, otp_instance)``. Only the hash is stored in the DB.
    """
    timeout_seconds: int = getattr(settings, "OTP_EXPIRY_SECONDS", 600)
    raw_code = f"{secrets.randbelow(1000000):06d}"
    code_hash = _hash_token(raw_code)
    expires_at = timezone.now() + timezone.timedelta(seconds=timeout_seconds)

    # Invalidate previous unused OTPs for this user & purpose
    OTP.objects.filter(user=user, purpose=purpose, used=False).update(used=True)

    otp_instance = OTP.objects.create(
        user=user,
        purpose=purpose,
        code_hash=code_hash,
        expires_at=expires_at,
        attempts=0,
    )
    return raw_code, otp_instance


def can_resend_otp(user: User, purpose: str = OTPPurpose.LOGIN) -> tuple[bool, int]:
    """
    Check if a new OTP can be requested according to cooldown limits.
    Returns ``(can_resend, remaining_cooldown_seconds)``.
    """
    cooldown_seconds: int = getattr(settings, "OTP_RESEND_COOLDOWN_SECONDS", 60)
    latest_otp = (
        OTP.objects.filter(user=user, purpose=purpose)
        .order_by("-created_at")
        .first()
    )
    if latest_otp:
        elapsed = (timezone.now() - latest_otp.created_at).total_seconds()
        if elapsed < cooldown_seconds:
            return False, int(cooldown_seconds - elapsed)
    return True, 0


def verify_otp(user: User, purpose: str, raw_code: str) -> tuple[bool, str, OTP | None]:
    """
    Validate *raw_code* against the active OTP for *user* and *purpose*.

    Performs constant-time HMAC comparison and tracks failed attempts.
    Returns ``(success, message, otp_instance)``.
    """
    if not raw_code:
        return False, "OTP code is required.", None

    otp_instance = (
        OTP.objects.filter(user=user, purpose=purpose, used=False)
        .order_by("-created_at")
        .first()
    )
    if otp_instance is None:
        return False, "Invalid or expired OTP.", None

    if otp_instance.is_expired:
        return False, "OTP has expired. Please request a new code.", None

    max_attempts: int = getattr(settings, "OTP_MAX_ATTEMPTS", 5)
    if otp_instance.attempts >= max_attempts:
        otp_instance.used = True
        otp_instance.save(update_fields=["used"])
        return False, "Maximum verification attempts exceeded. Please request a new OTP.", None

    expected_hash = otp_instance.code_hash
    actual_hash = _hash_token(raw_code.strip())

    if hmac.compare_digest(expected_hash, actual_hash):
        otp_instance.used = True
        otp_instance.save(update_fields=["used"])
        return True, "OTP verified successfully.", otp_instance
    else:
        otp_instance.attempts += 1
        if otp_instance.attempts >= max_attempts:
            otp_instance.used = True
            otp_instance.save(update_fields=["attempts", "used"])
            return False, "Maximum verification attempts exceeded. Please request a new OTP.", None
        otp_instance.save(update_fields=["attempts"])
        remaining = max_attempts - otp_instance.attempts
        return False, f"Invalid OTP code. {remaining} attempt(s) remaining.", None

