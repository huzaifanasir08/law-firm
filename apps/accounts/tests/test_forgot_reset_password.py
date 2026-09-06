"""
Tests for:
  POST /api/accounts/forgot-password/
  POST /api/accounts/reset-password/
"""

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import PasswordResetToken
from apps.accounts.tokens import generate_password_reset_token

User = get_user_model()

FORGOT_URL = "/api/accounts/forgot-password/"
RESET_URL = "/api/accounts/reset-password/"
REFRESH_URL = "/api/accounts/refresh/"

GENERIC_MSG = "If an account exists for this email, a password reset link has been sent."


@pytest.mark.django_db
class TestForgotPasswordView:
    # ── Existing email ────────────────────────────────────────────────────────

    def test_forgot_password_existing_email_returns_200(self, api_client, user):
        response = api_client.post(FORGOT_URL, {"email": user.email}, format="json")
        assert response.status_code == status.HTTP_200_OK

    def test_forgot_password_creates_reset_token(self, api_client, user):
        api_client.post(FORGOT_URL, {"email": user.email}, format="json")
        assert PasswordResetToken.objects.filter(user=user, used=False).exists()

    def test_forgot_password_returns_generic_message(self, api_client, user):
        response = api_client.post(FORGOT_URL, {"email": user.email}, format="json")
        assert response.data.get("message") == GENERIC_MSG

    # ── Non-existing email ────────────────────────────────────────────────────

    def test_forgot_password_nonexistent_email_returns_200(self, api_client):
        response = api_client.post(
            FORGOT_URL, {"email": "nobody@nowhere.com"}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK

    def test_forgot_password_nonexistent_email_same_generic_message(self, api_client, user):
        resp_real = api_client.post(FORGOT_URL, {"email": user.email}, format="json")
        resp_fake = api_client.post(
            FORGOT_URL, {"email": "ghost@nowhere.com"}, format="json"
        )
        # Same message, same status — no email enumeration possible
        assert resp_real.data.get("message") == resp_fake.data.get("message")
        assert resp_real.status_code == resp_fake.status_code

    def test_forgot_password_no_token_created_for_nonexistent_email(self, api_client):
        initial_count = PasswordResetToken.objects.count()
        api_client.post(FORGOT_URL, {"email": "ghost@example.com"}, format="json")
        assert PasswordResetToken.objects.count() == initial_count

    # ── Invalid input ─────────────────────────────────────────────────────────

    def test_forgot_password_invalid_email_format_returns_400(self, api_client):
        response = api_client.post(FORGOT_URL, {"email": "not-an-email"}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_forgot_password_missing_email_returns_400(self, api_client):
        response = api_client.post(FORGOT_URL, {}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestResetPasswordView:
    # ── Valid token ───────────────────────────────────────────────────────────

    def test_reset_password_valid_token_returns_200(self, api_client, user):
        raw_token, _ = generate_password_reset_token(user)
        response = api_client.post(
            RESET_URL,
            {"token": raw_token, "new_password": "BrandN3wP@ss!"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK

    def test_reset_password_valid_token_changes_password(self, api_client, user):
        raw_token, _ = generate_password_reset_token(user)
        api_client.post(
            RESET_URL,
            {"token": raw_token, "new_password": "BrandN3wP@ss!"},
            format="json",
        )
        user.refresh_from_db()
        assert user.check_password("BrandN3wP@ss!")

    def test_reset_password_success_message(self, api_client, user):
        raw_token, _ = generate_password_reset_token(user)
        response = api_client.post(
            RESET_URL,
            {"token": raw_token, "new_password": "BrandN3wP@ss!"},
            format="json",
        )
        assert "message" in response.data

    # ── Token is single-use ───────────────────────────────────────────────────

    def test_reset_password_token_marked_used_after_success(self, api_client, user):
        raw_token, token_instance = generate_password_reset_token(user)
        api_client.post(
            RESET_URL,
            {"token": raw_token, "new_password": "BrandN3wP@ss!"},
            format="json",
        )
        token_instance.refresh_from_db()
        assert token_instance.used is True

    def test_reset_password_used_token_rejected(self, api_client, user):
        raw_token, token_instance = generate_password_reset_token(user)
        # First use — succeeds
        api_client.post(
            RESET_URL,
            {"token": raw_token, "new_password": "BrandN3wP@ss!"},
            format="json",
        )
        # Second use — should fail
        response = api_client.post(
            RESET_URL,
            {"token": raw_token, "new_password": "AnotherP@ss1!"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    # ── Expired token ─────────────────────────────────────────────────────────

    def test_reset_password_expired_token_returns_400(self, api_client, user):
        raw_token, token_instance = generate_password_reset_token(user)
        # Manually expire the token
        token_instance.expires_at = timezone.now() - timezone.timedelta(seconds=1)
        token_instance.save(update_fields=["expires_at"])

        response = api_client.post(
            RESET_URL,
            {"token": raw_token, "new_password": "BrandN3wP@ss!"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    # ── Invalid token ─────────────────────────────────────────────────────────

    def test_reset_password_invalid_token_returns_400(self, api_client, user):
        response = api_client.post(
            RESET_URL,
            {"token": "completely-invalid-garbage", "new_password": "BrandN3wP@ss!"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    # ── Revokes refresh tokens ────────────────────────────────────────────────

    def test_reset_password_revokes_existing_refresh_tokens(self, api_client, user):
        old_refresh = str(RefreshToken.for_user(user))
        raw_token, _ = generate_password_reset_token(user)
        api_client.post(
            RESET_URL,
            {"token": raw_token, "new_password": "BrandN3wP@ss!"},
            format="json",
        )
        resp = api_client.post(REFRESH_URL, {"refresh": old_refresh}, format="json")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    # ── Weak new password ─────────────────────────────────────────────────────

    def test_reset_password_weak_password_returns_400(self, api_client, user):
        raw_token, _ = generate_password_reset_token(user)
        response = api_client.post(
            RESET_URL,
            {"token": raw_token, "new_password": "abc"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    # ── Missing fields ────────────────────────────────────────────────────────

    def test_reset_password_missing_token_returns_400(self, api_client):
        response = api_client.post(
            RESET_URL, {"new_password": "BrandN3wP@ss!"}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_reset_password_missing_new_password_returns_400(self, api_client, user):
        raw_token, _ = generate_password_reset_token(user)
        response = api_client.post(RESET_URL, {"token": raw_token}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
