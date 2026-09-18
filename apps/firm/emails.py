"""
Email utilities for the firm app.
"""

import html
import logging
from django.conf import settings
from django.core.mail import send_mail

from apps.accounts.models import User

logger = logging.getLogger(__name__)


def send_lawyer_welcome_email(user: User, raw_password: str, firm_name: str) -> None:
    """
    Send a welcome email with generated credentials to a newly onboarded lawyer.
    """
    frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000")
    login_url = f"{frontend_url}/login"

    safe_name = html.escape(user.name)
    safe_email = html.escape(user.email)
    safe_firm = html.escape(firm_name)
    safe_password = html.escape(raw_password)

    subject = f"Welcome to {firm_name} — Your Lawyer Account Has Been Created"
    message = (
        f"Hello {user.name},\n\n"
        f"You have been added as a Lawyer at {firm_name} on the Law Firm platform.\n\n"
        "Here are your login credentials:\n"
        f"Email: {user.email}\n"
        f"Temporary Password: {raw_password}\n\n"
        f"You can log in at: {login_url}\n\n"
        "For security reasons, please change your password immediately after your first login.\n\n"
        f"— The {firm_name} Team"
    )
    html_message = (
        f"<p>Hello <strong>{safe_name}</strong>,</p>"
        f"<p>You have been added as a Lawyer at <strong>{safe_firm}</strong> on the Law Firm platform.</p>"
        "<p>Here are your login credentials:</p>"
        "<ul>"
        f"<li><strong>Email:</strong> {safe_email}</li>"
        f"<li><strong>Temporary Password:</strong> <code>{safe_password}</code></li>"
        "</ul>"
        f'<p><a href="{login_url}">Log in to your account</a></p>'
        "<p>For security reasons, please change your password immediately after your first login.</p>"
        f"<p>— The {safe_firm} Team</p>"
    )

    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html_message,
        fail_silently=False,
    )
