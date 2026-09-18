"""
Email utilities for the administration app.
"""

import html
from django.conf import settings
from django.core.mail import send_mail

from apps.accounts.models import User


def send_admin_user_welcome_email(user: User, raw_password: str) -> None:
    """
    Send a welcome email with generated credentials to newly created user.

    The email is sent via the configured EMAIL_BACKEND.
    """
    frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000")
    login_url = f"{frontend_url}/login"

    safe_name = html.escape(user.name)
    safe_email = html.escape(user.email)
    safe_role = html.escape(user.get_role_display() if hasattr(user, "get_role_display") else user.role)
    safe_password = html.escape(raw_password)

    subject = "Your Law Firm Account Has Been Created"
    message = (
        f"Hello {user.name},\n\n"
        f"An account has been created for you on the Law Firm platform with the role: {user.role}.\n\n"
        "Here are your login credentials:\n"
        f"Email: {user.email}\n"
        f"Temporary Password: {raw_password}\n\n"
        f"You can log in at: {login_url}\n\n"
        "We recommend changing your password after logging in for the first time.\n\n"
        "— The Law Firm Team"
    )
    html_message = (
        f"<p>Hello <strong>{safe_name}</strong>,</p>"
        f"<p>An account has been created for you on the Law Firm platform with the role: <strong>{safe_role}</strong>.</p>"
        "<p>Here are your login credentials:</p>"
        "<ul>"
        f"<li><strong>Email:</strong> {safe_email}</li>"
        f"<li><strong>Temporary Password:</strong> <code>{safe_password}</code></li>"
        "</ul>"
        f'<p><a href="{login_url}">Log in to your account</a></p>'
        "<p>We recommend changing your password after logging in for the first time.</p>"
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
