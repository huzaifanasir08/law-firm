"""
Tests for POST /api/accounts/logout/
"""

import pytest
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

LOGOUT_URL = "/api/accounts/logout/"
REFRESH_URL = "/api/accounts/refresh/"
ME_URL = "/api/accounts/me/"


@pytest.mark.django_db
class TestLogoutView:
    # ── Valid logout ──────────────────────────────────────────────────────────

    def test_logout_returns_200(self, auth_client, user):
        refresh = RefreshToken.for_user(user)
        response = auth_client.post(
            LOGOUT_URL, {"refresh": str(refresh)}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK

    def test_logout_returns_success_message(self, auth_client, user):
        refresh = RefreshToken.for_user(user)
        response = auth_client.post(
            LOGOUT_URL, {"refresh": str(refresh)}, format="json"
        )
        assert "message" in response.data

    # ── Token revocation ──────────────────────────────────────────────────────

    def test_blacklisted_refresh_token_cannot_be_reused(self, auth_client, api_client, user):
        refresh = RefreshToken.for_user(user)
        raw_refresh = str(refresh)

        # Logout (blacklist the token)
        auth_client.post(LOGOUT_URL, {"refresh": raw_refresh}, format="json")

        # Attempt to refresh with the same token
        response = api_client.post(REFRESH_URL, {"refresh": raw_refresh}, format="json")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_blacklisted_refresh_token_reuse_attempt_rejected_again(
        self, auth_client, api_client, user
    ):
        refresh = RefreshToken.for_user(user)
        raw_refresh = str(refresh)

        auth_client.post(LOGOUT_URL, {"refresh": raw_refresh}, format="json")

        # Second attempt also fails
        response = api_client.post(REFRESH_URL, {"refresh": raw_refresh}, format="json")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    # ── Missing / invalid token ───────────────────────────────────────────────

    def test_logout_missing_refresh_token_returns_400(self, auth_client):
        response = auth_client.post(LOGOUT_URL, {}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_logout_invalid_refresh_token_returns_400(self, auth_client):
        response = auth_client.post(
            LOGOUT_URL, {"refresh": "this.is.not.a.token"}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    # ── Unauthenticated logout ────────────────────────────────────────────────

    def test_logout_unauthenticated_returns_401(self, api_client, user):
        refresh = RefreshToken.for_user(user)
        response = api_client.post(
            LOGOUT_URL, {"refresh": str(refresh)}, format="json"
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
