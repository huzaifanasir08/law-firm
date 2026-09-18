"""
Tests for Two-Factor Authentication (2FA) login flows and enable/disable operations.
"""

import pytest
from django.core import mail
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import OTPPurpose
from apps.accounts.tokens import generate_otp

LOGIN_URL = "/api/accounts/login/"
OTP_VERIFY_URL = "/api/accounts/otp/verify/"
REQUEST_2FA_CHANGE_URL = "/api/accounts/2fa/request-change/"
CONFIRM_2FA_CHANGE_URL = "/api/accounts/2fa/confirm-change/"


@pytest.mark.django_db
class TestTwoFactorLoginFlow:
    def test_login_with_2fa_disabled_returns_tokens_immediately(self, api_client, make_user):
        user = make_user(email="no2fa@example.com", password="Password123!", two_factor_enabled=False)
        response = api_client.post(
            LOGIN_URL,
            {"email": "no2fa@example.com", "password": "Password123!"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data.get("requires_2fa") is False
        assert "access" in response.data
        assert "refresh" in response.data
        assert len(mail.outbox) == 0

    def test_login_with_2fa_enabled_blocks_tokens_and_sends_otp(self, api_client, make_user):
        user = make_user(email="has2fa@example.com", password="Password123!", two_factor_enabled=True)
        response = api_client.post(
            LOGIN_URL,
            {"email": "has2fa@example.com", "password": "Password123!"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data.get("requires_2fa") is True
        assert "otp_session_token" in response.data
        assert "access" not in response.data
        assert "refresh" not in response.data

        # Verify email was dispatched
        assert len(mail.outbox) == 1
        assert "Login Verification Code" in mail.outbox[0].subject
        assert user.email in mail.outbox[0].to

    def test_login_completed_after_otp_verification(self, api_client, make_user):
        user = make_user(email="flow2fa@example.com", password="Password123!", two_factor_enabled=True)
        login_resp = api_client.post(
            LOGIN_URL,
            {"email": "flow2fa@example.com", "password": "Password123!"},
            format="json",
        )
        session_token = login_resp.data["otp_session_token"]

        # User checks their email for the OTP code
        email_body = mail.outbox[0].body
        # We can also get the latest OTP directly
        otp_record = user.otps.filter(purpose=OTPPurpose.LOGIN, used=False).first()
        assert otp_record is not None

        # Verify with a newly generated OTP for test reproducibility
        raw_code, _ = generate_otp(user, purpose=OTPPurpose.LOGIN)
        verify_resp = api_client.post(
            OTP_VERIFY_URL,
            {"otp_session_token": session_token, "code": raw_code},
            format="json",
        )
        assert verify_resp.status_code == status.HTTP_200_OK
        assert "access" in verify_resp.data
        assert "refresh" in verify_resp.data
        assert verify_resp.data["user"]["email"] == "flow2fa@example.com"

    def test_login_blocked_with_wrong_otp(self, api_client, make_user):
        user = make_user(email="wrongotp@example.com", password="Password123!", two_factor_enabled=True)
        login_resp = api_client.post(
            LOGIN_URL,
            {"email": "wrongotp@example.com", "password": "Password123!"},
            format="json",
        )
        session_token = login_resp.data["otp_session_token"]

        verify_resp = api_client.post(
            OTP_VERIFY_URL,
            {"otp_session_token": session_token, "code": "000000"},
            format="json",
        )
        assert verify_resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "access" not in verify_resp.data


@pytest.mark.django_db
class TestTwoFactorSettingsManagement:
    def test_enable_2fa_requires_otp(self, auth_client, user):
        assert user.two_factor_enabled is False

        # Step 1: Request change sends OTP
        req_resp = auth_client.post(REQUEST_2FA_CHANGE_URL, {}, format="json")
        assert req_resp.status_code == status.HTTP_200_OK
        assert len(mail.outbox) == 1
        assert "Change 2FA" in mail.outbox[0].subject

        # Check that 2FA is NOT yet enabled before confirmation
        user.refresh_from_db()
        assert user.two_factor_enabled is False

        # Step 2: Confirm with correct OTP
        raw_code, _ = generate_otp(user, purpose=OTPPurpose.CHANGE_2FA)
        confirm_resp = auth_client.post(
            CONFIRM_2FA_CHANGE_URL,
            {"code": raw_code, "enable": True},
            format="json",
        )
        assert confirm_resp.status_code == status.HTTP_200_OK
        assert confirm_resp.data["two_factor_enabled"] is True

        user.refresh_from_db()
        assert user.two_factor_enabled is True

        # Status change notification email should have been sent
        assert len(mail.outbox) == 2
        assert "ENABLED" in mail.outbox[1].subject

    def test_enable_2fa_fails_with_wrong_otp(self, auth_client, user):
        auth_client.post(REQUEST_2FA_CHANGE_URL, {}, format="json")
        confirm_resp = auth_client.post(
            CONFIRM_2FA_CHANGE_URL,
            {"code": "000000", "enable": True},
            format="json",
        )
        assert confirm_resp.status_code == status.HTTP_400_BAD_REQUEST
        user.refresh_from_db()
        assert user.two_factor_enabled is False

    def test_disable_2fa_requires_otp(self, auth_client, user):
        user.two_factor_enabled = True
        user.save(update_fields=["two_factor_enabled"])

        # Step 1: Request change
        auth_client.post(REQUEST_2FA_CHANGE_URL, {}, format="json")
        user.refresh_from_db()
        assert user.two_factor_enabled is True

        # Step 2: Confirm disable with OTP
        raw_code, _ = generate_otp(user, purpose=OTPPurpose.CHANGE_2FA)
        confirm_resp = auth_client.post(
            CONFIRM_2FA_CHANGE_URL,
            {"code": raw_code, "enable": False},
            format="json",
        )
        assert confirm_resp.status_code == status.HTTP_200_OK
        assert confirm_resp.data["two_factor_enabled"] is False

        user.refresh_from_db()
        assert user.two_factor_enabled is False
        assert "DISABLED" in mail.outbox[-1].subject

    def test_unauthenticated_cannot_request_or_change_2fa(self, api_client):
        resp1 = api_client.post(REQUEST_2FA_CHANGE_URL, {}, format="json")
        assert resp1.status_code == status.HTTP_401_UNAUTHORIZED

        resp2 = api_client.post(CONFIRM_2FA_CHANGE_URL, {"code": "123456", "enable": True}, format="json")
        assert resp2.status_code == status.HTTP_401_UNAUTHORIZED

    def test_user_cannot_modify_other_user_2fa(self, api_client, make_user):
        user_a = make_user(email="user_a@example.com", password="Password123!")
        user_b = make_user(email="user_b@example.com", password="Password123!")

        # Client authenticated as user_a
        refresh = RefreshToken.for_user(user_a)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

        raw_code_b, _ = generate_otp(user_b, purpose=OTPPurpose.CHANGE_2FA)

        # Trying to submit user_b's code as user_a fails because code belongs to user_b
        confirm_resp = api_client.post(
            CONFIRM_2FA_CHANGE_URL,
            {"code": raw_code_b, "enable": True},
            format="json",
        )
        assert confirm_resp.status_code == status.HTTP_400_BAD_REQUEST
        user_b.refresh_from_db()
        assert user_b.two_factor_enabled is False

