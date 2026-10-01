"""
Email utilities for the clerk app.
"""

import html
import logging
from django.conf import settings
from django.core.mail import send_mail

from apps.accounts.models import User

logger = logging.getLogger(__name__)


def send_clerk_welcome_email(
    user: User, raw_password: str, firm_name: str, lawyer_name: str | None = None
) -> None:
    """
    Send a welcome email with generated credentials to a newly onboarded clerk.
    """
    frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000")
    login_url = f"{frontend_url}/login"

    safe_name = html.escape(user.name)
    safe_email = html.escape(user.email)
    safe_firm = html.escape(firm_name)
    safe_password = html.escape(raw_password)
    safe_lawyer = html.escape(lawyer_name) if lawyer_name else None

    subject = f"Welcome to {firm_name} — Your Clerk Account Has Been Created"

    lawyer_line_txt = f" under lawyer {lawyer_name}" if lawyer_name else ""
    lawyer_line_html = f" under lawyer <strong>{safe_lawyer}</strong>" if safe_lawyer else ""

    message = (
        f"Hello {user.name},\n\n"
        f"You have been added as a Clerk at {firm_name}{lawyer_line_txt} on the Law Firm platform.\n\n"
        "Here are your login credentials:\n"
        f"Email: {user.email}\n"
        f"Temporary Password: {raw_password}\n\n"
        f"You can log in at: {login_url}\n\n"
        "For security reasons, please change your password immediately after your first login.\n\n"
        f"— The {firm_name} Team"
    )
    html_message = (
        f"<p>Hello <strong>{safe_name}</strong>,</p>"
        f"<p>You have been added as a Clerk at <strong>{safe_firm}</strong>{lawyer_line_html} on the Law Firm platform.</p>"
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
