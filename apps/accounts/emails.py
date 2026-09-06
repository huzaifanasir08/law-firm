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
