"""
Email utilities for the accounts app.
"""

from django.conf import settings
from django.core.mail import send_mail

from .models import User


def send_password_reset_email(user: User, raw_token: str) -> None:
    """
    Send a password-reset email to *user* containing a link that embeds
    *raw_token* as a query parameter.

    The email is sent via whatever backend is configured in
    ``settings.EMAIL_BACKEND`` — console backend in development,
    SMTP in production.
    """
    frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000")
    reset_url = f"{frontend_url}/reset-password?token={raw_token}"

    subject = "Password Reset Request — Law Firm"
    message = (
        f"Hello {user.name},\n\n"
        "We received a request to reset your password.\n\n"
        f"Click the link below to set a new password (valid for 1 hour):\n"
        f"{reset_url}\n\n"
        "If you did not request a password reset, you can safely ignore this email.\n\n"
        "— The Law Firm Team"
    )
    html_message = (
        f"<p>Hello <strong>{user.name}</strong>,</p>"
        "<p>We received a request to reset your password.</p>"
        f'<p><a href="{reset_url}">Reset my password</a></p>'
        "<p>This link expires in <strong>1 hour</strong>.</p>"
        "<p>If you did not request a password reset, you can safely ignore this email.</p>"
        "<p>— The Law Firm Team</p>"
    )

    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html_message,
        fail_silently=False,
    )


import html
from .models import OTPPurpose


def send_otp_email(user: User, raw_code: str, purpose: str = OTPPurpose.LOGIN) -> None:
    """
    Send an OTP verification email to *user*.

    Includes the 6-digit code, expiration duration, and security advisory.
    """
    timeout_minutes = int(getattr(settings, "OTP_EXPIRY_SECONDS", 600) / 60)
    safe_name = html.escape(user.name)
    safe_code = html.escape(raw_code)

    if purpose == OTPPurpose.CHANGE_2FA:
        action_text = "modify your Two-Factor Authentication (2FA) settings"
        subject = "Verification Code: Change 2FA Settings — Law Firm"
    else:
        action_text = "log into your Law Firm account"
        subject = "Your Login Verification Code — Law Firm"

    message = (
        f"Hello {user.name},\n\n"
        f"Your verification code to {action_text} is:\n\n"
        f"    {raw_code}\n\n"
        f"This code will expire in {timeout_minutes} minutes.\n\n"
        "SECURITY WARNING: Never share this code with anyone. Our staff will never ask for your verification code.\n\n"
        "If you did not request this verification code, please secure your account immediately.\n\n"
        "— The Law Firm Team"
    )

    html_message = (
        f"<p>Hello <strong>{safe_name}</strong>,</p>"
        f"<p>Your verification code to {action_text} is:</p>"
        f'<p style="font-size: 24px; font-weight: bold; letter-spacing: 4px; color: #1e3a8a;">{safe_code}</p>'
        f"<p>This code will expire in <strong>{timeout_minutes} minutes</strong>.</p>"
        '<p style="color: #b91c1c;"><strong>SECURITY WARNING:</strong> Never share this code with anyone. '
        "Our staff will never ask for your verification code.</p>"
        "<p>If you did not request this verification code, please secure your account immediately.</p>"
        "<p>— The Law Firm Team</p>"
    )

    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html_message,
        fail_silently=False,
    )


def send_2fa_status_change_email(user: User, enabled: bool) -> None:
    """
    Send a security notification email when 2FA is enabled or disabled.
    """
    safe_name = html.escape(user.name)
    status_text = "ENABLED" if enabled else "DISABLED"
    subject = f"Security Alert: Two-Factor Authentication {status_text} — Law Firm"

    if enabled:
        desc = "Two-Factor Authentication has been successfully enabled on your account. You will now be required to enter an OTP code sent to this email upon login."
    else:
        desc = "Two-Factor Authentication has been DISABLED on your account. If you did not perform this change, please change your password immediately."

    message = (
        f"Hello {user.name},\n\n"
        f"This is a security confirmation that Two-Factor Authentication has been {status_text} for your account.\n\n"
        f"{desc}\n\n"
        "— The Law Firm Team"
    )

    html_message = (
        f"<p>Hello <strong>{safe_name}</strong>,</p>"
        f"<p>This is a security confirmation that Two-Factor Authentication has been <strong>{status_text}</strong> for your account.</p>"
        f"<p>{desc}</p>"
        "<p>— The Law Firm Team</p>"
    )

    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html_message,
        fail_silently=False,
    )

