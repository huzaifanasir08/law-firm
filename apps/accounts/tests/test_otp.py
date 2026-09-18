"""
Tests for OTP generation, validation, rate limiting, and endpoints.
"""

import pytest
from django.conf import settings
from django.core import mail
from django.utils import timezone
from rest_framework import status

from apps.accounts.models import OTP, OTPPurpose
from apps.accounts.tokens import can_resend_otp, generate_otp, verify_otp, _hash_token, OTPSessionToken

OTP_SEND_URL = "/api/accounts/otp/send/"
OTP_RESEND_URL = "/api/accounts/otp/resend/"
OTP_VERIFY_URL = "/api/accounts/otp/verify/"


@pytest.mark.django_db
class TestOTPUtilities:
    def test_otp_generation(self, user):
        raw_code, otp_record = generate_otp(user, purpose=OTPPurpose.LOGIN)
        assert len(raw_code) == 6
        assert raw_code.isdigit()
        assert otp_record.user == user
        assert otp_record.purpose == OTPPurpose.LOGIN
        assert not otp_record.used
        assert otp_record.attempts == 0
        # Code hash should match HMAC-SHA256, raw code is NOT stored
        assert otp_record.code_hash == _hash_token(raw_code)
        assert raw_code not in otp_record.code_hash

    def test_otp_correct_verification(self, user):
        raw_code, otp_record = generate_otp(user, purpose=OTPPurpose.LOGIN)
        success, message, verified = verify_otp(user, OTPPurpose.LOGIN, raw_code)
        assert success is True
        assert verified.id == otp_record.id
        otp_record.refresh_from_db()
        assert otp_record.used is True

    def test_invalid_otp_fails_and_increments_attempts(self, user):
        raw_code, otp_record = generate_otp(user, purpose=OTPPurpose.LOGIN)
        success, message, verified = verify_otp(user, OTPPurpose.LOGIN, "000000" if raw_code != "000000" else "111111")
        assert success is False
        assert verified is None
        assert "Invalid OTP code" in message
        otp_record.refresh_from_db()
        assert otp_record.attempts == 1
        assert otp_record.used is False

    def test_otp_expiration(self, user):
        raw_code, otp_record = generate_otp(user, purpose=OTPPurpose.LOGIN)
        # Manually expire the OTP
        otp_record.expires_at = timezone.now() - timezone.timedelta(seconds=10)
        otp_record.save(update_fields=["expires_at"])

        success, message, verified = verify_otp(user, OTPPurpose.LOGIN, raw_code)
        assert success is False
        assert "expired" in message.lower()

    def test_otp_single_use_behavior(self, user):
        raw_code, otp_record = generate_otp(user, purpose=OTPPurpose.LOGIN)
        # First use succeeds
        success1, _, _ = verify_otp(user, OTPPurpose.LOGIN, raw_code)
        assert success1 is True

        # Second use fails because used=True
        success2, message, _ = verify_otp(user, OTPPurpose.LOGIN, raw_code)
        assert success2 is False
        assert "invalid" in message.lower() or "expired" in message.lower()

    def test_otp_attempt_limit_locks_otp(self, user):
        raw_code, otp_record = generate_otp(user, purpose=OTPPurpose.LOGIN)
        max_attempts = getattr(settings, "OTP_MAX_ATTEMPTS", 5)

        for i in range(max_attempts - 1):
            success, msg, _ = verify_otp(user, OTPPurpose.LOGIN, "999999")
            assert success is False
            assert "remaining" in msg

        # Final wrong attempt reaches max limit
        success, msg, _ = verify_otp(user, OTPPurpose.LOGIN, "999999")
        assert success is False
        assert "Maximum verification attempts exceeded" in msg

        otp_record.refresh_from_db()
        assert otp_record.used is True

        # Even correct code now fails because OTP is locked
        success_correct, _, _ = verify_otp(user, OTPPurpose.LOGIN, raw_code)
        assert success_correct is False

    def test_new_otp_invalidates_previous_otp(self, user):
        raw_code_1, otp_1 = generate_otp(user, purpose=OTPPurpose.LOGIN)
        raw_code_2, otp_2 = generate_otp(user, purpose=OTPPurpose.LOGIN)

        otp_1.refresh_from_db()
        assert otp_1.used is True

        # First code cannot be verified anymore
        success1, _, _ = verify_otp(user, OTPPurpose.LOGIN, raw_code_1)
        assert success1 is False

        # Second code succeeds
        success2, _, _ = verify_otp(user, OTPPurpose.LOGIN, raw_code_2)
        assert success2 is True

    def test_resend_cooldown(self, user):
        generate_otp(user, purpose=OTPPurpose.LOGIN)
        can_resend, remaining = can_resend_otp(user, purpose=OTPPurpose.LOGIN)
        assert can_resend is False
        assert remaining > 0


@pytest.mark.django_db
class TestOTPEndpoints:
    def test_otp_send_with_email(self, api_client, user):
        response = api_client.post(OTP_SEND_URL, {"email": user.email}, format="json")
        assert response.status_code == status.HTTP_200_OK
        assert len(mail.outbox) == 1
        assert "Verification Code" in mail.outbox[0].subject or "Your Login Verification Code" in mail.outbox[0].subject

    def test_otp_send_with_session_token(self, api_client, user):
        session_token = str(OTPSessionToken.for_user(user))
        response = api_client.post(OTP_SEND_URL, {"otp_session_token": session_token}, format="json")
        assert response.status_code == status.HTTP_200_OK
        assert len(mail.outbox) == 1

    def test_otp_resend_endpoint_cooldown(self, api_client, user):
        session_token = str(OTPSessionToken.for_user(user))
        # Initial send
        resp1 = api_client.post(OTP_SEND_URL, {"otp_session_token": session_token}, format="json")
        assert resp1.status_code == status.HTTP_200_OK

        # Immediate resend should trigger cooldown 429
        resp2 = api_client.post(OTP_RESEND_URL, {"otp_session_token": session_token}, format="json")
        assert resp2.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert "seconds" in resp2.data.get("error", "")

    def test_otp_verify_success_returns_jwt(self, api_client, user):
        session_token = str(OTPSessionToken.for_user(user))
        raw_code, _ = generate_otp(user, purpose=OTPPurpose.LOGIN)

        response = api_client.post(
            OTP_VERIFY_URL,
            {"otp_session_token": session_token, "code": raw_code},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data
        assert "refresh" in response.data
        assert response.data["user"]["email"] == user.email


    def test_otp_verify_wrong_code_returns_400(self, api_client, user):
        session_token = str(OTPSessionToken.for_user(user))
        generate_otp(user, purpose=OTPPurpose.LOGIN)

        response = api_client.post(
            OTP_VERIFY_URL,
            {"otp_session_token": session_token, "code": "000000"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "access" not in response.data
