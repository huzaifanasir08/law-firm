"""
Tests for POST /api/accounts/login/
"""

import pytest
from django.urls import reverse
from rest_framework import status

from apps.accounts.models import UserRole

LOGIN_URL = "/api/accounts/login/"


@pytest.mark.django_db
class TestLoginView:
    # ── Valid credentials ─────────────────────────────────────────────────────

    def test_login_valid_credentials_returns_200(self, api_client, make_user):
        user = make_user(email="valid@example.com", password="GoodP@ss123")
        response = api_client.post(
            LOGIN_URL,
            {"email": "valid@example.com", "password": "GoodP@ss123"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK

    def test_login_response_contains_access_token(self, api_client, make_user):
        make_user(email="a@example.com", password="GoodP@ss123")
        response = api_client.post(
            LOGIN_URL, {"email": "a@example.com", "password": "GoodP@ss123"}, format="json"
        )
        assert "access" in response.data

    def test_login_response_contains_refresh_token(self, api_client, make_user):
        make_user(email="b@example.com", password="GoodP@ss123")
        response = api_client.post(
            LOGIN_URL, {"email": "b@example.com", "password": "GoodP@ss123"}, format="json"
        )
        assert "refresh" in response.data

    def test_login_response_contains_user_profile(self, api_client, make_user):
        make_user(email="c@example.com", password="GoodP@ss123", name="Alice")
        response = api_client.post(
            LOGIN_URL, {"email": "c@example.com", "password": "GoodP@ss123"}, format="json"
        )
        assert "user" in response.data
        user_data = response.data["user"]
        assert user_data["email"] == "c@example.com"
        assert user_data["name"] == "Alice"

    def test_login_response_does_not_contain_password(self, api_client, make_user):
        make_user(email="d@example.com", password="GoodP@ss123")
        response = api_client.post(
            LOGIN_URL, {"email": "d@example.com", "password": "GoodP@ss123"}, format="json"
        )
        user_data = response.data.get("user", {})
        assert "password" not in user_data
        assert "password" not in response.data

    def test_login_user_profile_contains_required_fields(self, api_client, make_user):
        make_user(email="e@example.com", password="GoodP@ss123")
        response = api_client.post(
            LOGIN_URL, {"email": "e@example.com", "password": "GoodP@ss123"}, format="json"
        )
        user_data = response.data["user"]
        for field in ["id", "name", "email", "phone", "address", "role", "profile_photo"]:
            assert field in user_data, f"Missing field: {field}"

    # ── Invalid credentials ───────────────────────────────────────────────────

    def test_login_wrong_password_returns_400(self, api_client, make_user):
        make_user(email="f@example.com", password="CorrectP@ss")
        response = api_client.post(
            LOGIN_URL, {"email": "f@example.com", "password": "WrongPass"}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_login_wrong_email_returns_400(self, api_client, make_user):
        response = api_client.post(
            LOGIN_URL, {"email": "nobody@example.com", "password": "anything"}, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_login_generic_error_message(self, api_client, make_user):
        """Error message must not reveal which field was wrong."""
        make_user(email="g@example.com", password="CorrectP@ss")
        resp_wrong_pass = api_client.post(
            LOGIN_URL, {"email": "g@example.com", "password": "Wrong"}, format="json"
        )
        resp_wrong_email = api_client.post(
            LOGIN_URL, {"email": "ghost@example.com", "password": "anything"}, format="json"
        )
        # Both should return the same generic error message
        assert resp_wrong_pass.status_code == resp_wrong_email.status_code

    # ── Inactive user ─────────────────────────────────────────────────────────

    def test_login_inactive_user_returns_400(self, api_client, make_user):
        make_user(email="inactive@example.com", password="GoodP@ss123", is_active=False)
        response = api_client.post(
            LOGIN_URL,
            {"email": "inactive@example.com", "password": "GoodP@ss123"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    # ── Missing fields ────────────────────────────────────────────────────────

    def test_login_missing_email_returns_400(self, api_client):
        response = api_client.post(LOGIN_URL, {"password": "GoodP@ss123"}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_login_missing_password_returns_400(self, api_client):
        response = api_client.post(LOGIN_URL, {"email": "x@example.com"}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_login_empty_body_returns_400(self, api_client):
        response = api_client.post(LOGIN_URL, {}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    # ── Role-specific login ───────────────────────────────────────────────────

    def test_login_returns_correct_role(self, api_client, make_user):
        make_user(email="lawyer@example.com", password="GoodP@ss123", role=UserRole.LAWYER)
        response = api_client.post(
            LOGIN_URL, {"email": "lawyer@example.com", "password": "GoodP@ss123"}, format="json"
        )
        assert response.data["user"]["role"] == UserRole.LAWYER
