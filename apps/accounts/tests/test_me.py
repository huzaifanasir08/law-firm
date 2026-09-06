"""
Tests for GET /api/accounts/me/
"""

import pytest
from rest_framework import status

ME_URL = "/api/accounts/me/"


@pytest.mark.django_db
class TestMeView:
    # ── Authenticated request ─────────────────────────────────────────────────

    def test_me_authenticated_returns_200(self, auth_client):
        response = auth_client.get(ME_URL)
        assert response.status_code == status.HTTP_200_OK

    def test_me_returns_correct_user(self, auth_client):
        user = auth_client._user
        response = auth_client.get(ME_URL)
        assert response.data["email"] == user.email
        assert response.data["name"] == user.name

    def test_me_contains_all_profile_fields(self, auth_client):
        response = auth_client.get(ME_URL)
        expected_fields = [
            "id", "name", "email", "phone", "address",
            "role", "profile_photo", "is_active",
            "created_at", "updated_at", "last_login",
        ]
        for field in expected_fields:
            assert field in response.data, f"Missing field: {field}"

    def test_me_does_not_expose_password(self, auth_client):
        response = auth_client.get(ME_URL)
        assert "password" not in response.data

    def test_me_returns_self_not_other_user(self, auth_client, make_user):
        other = make_user(email="other@example.com")
        response = auth_client.get(ME_URL)
        assert response.data["email"] != other.email
        assert response.data["email"] == auth_client._user.email

    # ── Unauthenticated request ───────────────────────────────────────────────

    def test_me_unauthenticated_returns_401(self, api_client):
        response = api_client.get(ME_URL)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_me_with_invalid_token_returns_401(self, api_client):
        api_client.credentials(HTTP_AUTHORIZATION="Bearer totally.invalid.token")
        response = api_client.get(ME_URL)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
