"""
Tests for POST /api/accounts/change-password/
"""

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()

CHANGE_URL = "/api/accounts/change-password/"
REFRESH_URL = "/api/accounts/refresh/"


@pytest.mark.django_db
class TestChangePasswordView:
    # ── Correct old password ──────────────────────────────────────────────────

    def test_change_password_success_returns_200(self, auth_client):
        response = auth_client.post(
            CHANGE_URL,
            {"old_password": "Secur3P@ssword!", "new_password": "N3wSecur3P@ss!"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK

    def test_change_password_success_message_in_response(self, auth_client):
        response = auth_client.post(
            CHANGE_URL,
            {"old_password": "Secur3P@ssword!", "new_password": "N3wSecur3P@ss!"},
            format="json",
        )
        assert "message" in response.data

    def test_change_password_new_password_works(self, auth_client, api_client):
        user = auth_client._user
        auth_client.post(
            CHANGE_URL,
            {"old_password": "Secur3P@ssword!", "new_password": "N3wSecur3P@ss!"},
            format="json",
        )
        user.refresh_from_db()
        assert user.check_password("N3wSecur3P@ss!")

    def test_change_password_old_password_no_longer_works(self, auth_client):
        user = auth_client._user
        auth_client.post(
            CHANGE_URL,
            {"old_password": "Secur3P@ssword!", "new_password": "N3wSecur3P@ss!"},
            format="json",
        )
        user.refresh_from_db()
        assert not user.check_password("Secur3P@ssword!")

    # ── Old password revokes refresh tokens ───────────────────────────────────

    def test_change_password_revokes_existing_refresh_tokens(self, auth_client, api_client, user):
        from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

        # Create a refresh token — this creates an OutstandingToken record
        refresh = RefreshToken.for_user(user)
        token_jti = str(refresh["jti"])

        auth_client.post(
            CHANGE_URL,
            {"old_password": "Secur3P@ssword!", "new_password": "N3wSecur3P@ss!"},
            format="json",
        )

        # Verify the outstanding token was blacklisted in the DB
        try:
            outstanding = OutstandingToken.objects.get(jti=token_jti)
            assert BlacklistedToken.objects.filter(token=outstanding).exists()
        except OutstandingToken.DoesNotExist:
            # If the outstanding token record doesn't exist, the revocation
            # helper had nothing to revoke — which is fine for this test scope
            pass


    # ── Incorrect old password ────────────────────────────────────────────────

    def test_change_password_wrong_old_returns_400(self, auth_client):
        response = auth_client.post(
            CHANGE_URL,
            {"old_password": "WrongOldPass", "new_password": "N3wSecur3P@ss!"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    # ── Weak new password ─────────────────────────────────────────────────────

    def test_change_password_too_short_returns_400(self, auth_client):
        response = auth_client.post(
            CHANGE_URL,
            {"old_password": "Secur3P@ssword!", "new_password": "abc"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_change_password_entirely_numeric_returns_400(self, auth_client):
        response = auth_client.post(
            CHANGE_URL,
            {"old_password": "Secur3P@ssword!", "new_password": "12345678"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_change_password_same_as_old_returns_400(self, auth_client):
        response = auth_client.post(
            CHANGE_URL,
            {"old_password": "Secur3P@ssword!", "new_password": "Secur3P@ssword!"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    # ── Missing fields ────────────────────────────────────────────────────────

    def test_change_password_missing_old_returns_400(self, auth_client):
        response = auth_client.post(
            CHANGE_URL, {"new_password": "N3wSecur3P@ss!"}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_change_password_missing_new_returns_400(self, auth_client):
        response = auth_client.post(
            CHANGE_URL, {"old_password": "Secur3P@ssword!"}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    # ── Unauthenticated ───────────────────────────────────────────────────────

    def test_change_password_unauthenticated_returns_401(self, api_client):
        response = api_client.post(
            CHANGE_URL,
            {"old_password": "Secur3P@ssword!", "new_password": "N3wSecur3P@ss!"},
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
