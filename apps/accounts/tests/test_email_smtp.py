"""
Tests for SMTP / Email configuration and email utility functions.
"""

import pytest
from django.conf import settings
from django.core import mail

from apps.accounts.emails import (
    send_2fa_status_change_email,
    send_otp_email,
    send_password_reset_email,
)
from apps.accounts.models import OTPPurpose
from apps.administration.emails import send_admin_user_welcome_email


def test_smtp_configuration_settings():
    """Verify SMTP configuration parameters adhere to specifications."""
    assert settings.EMAIL_HOST == "smtp.gmail.com"
    assert settings.EMAIL_PORT == 587
    assert settings.EMAIL_USE_TLS is True
    assert settings.EMAIL_HOST_USER == "huzaifanasirfab@gmail.com"
    assert settings.DEFAULT_FROM_EMAIL == "huzaifanasirfab@gmail.com"


@pytest.mark.django_db
class TestEmailTemplatesAndSending:
    def test_account_creation_welcome_email(self, user):
        send_admin_user_welcome_email(user, "TempPass123!")
        assert len(mail.outbox) == 1
        email = mail.outbox[0]
        assert email.to == [user.email]
        assert email.from_email == settings.DEFAULT_FROM_EMAIL
        assert "Your Law Firm Account Has Been Created" in email.subject
        assert "TempPass123!" in email.body
        assert "login" in email.body.lower()

    def test_password_reset_email(self, user):
        send_password_reset_email(user, "mock_token_abc123")
        assert len(mail.outbox) == 1
        email = mail.outbox[0]
        assert email.to == [user.email]
        assert email.from_email == settings.DEFAULT_FROM_EMAIL
        assert "Password Reset Request" in email.subject
        assert "mock_token_abc123" in email.body
        assert "1 hour" in email.body

    def test_otp_email_format_and_security_warning(self, user):
        send_otp_email(user, "654321", purpose=OTPPurpose.LOGIN)
        assert len(mail.outbox) == 1
        email = mail.outbox[0]
        assert email.to == [user.email]
        assert email.from_email == settings.DEFAULT_FROM_EMAIL
        assert "654321" in email.body
        assert "SECURITY WARNING" in email.body
        assert "expire" in email.body.lower()

    def test_2fa_status_change_email_enabled_and_disabled(self, user):
        send_2fa_status_change_email(user, enabled=True)
        assert len(mail.outbox) == 1
        assert "ENABLED" in mail.outbox[0].subject

        send_2fa_status_change_email(user, enabled=False)
        assert len(mail.outbox) == 2
        assert "DISABLED" in mail.outbox[1].subject
