"""
Tests for Admin User Management API:
- POST /api/admin/users/ (Create user with role FIRM_ADMIN or SUPER_ADMIN)
- GET /api/admin/users/ (List with pagination, search, filter, excluding self)
- GET /api/admin/users/<id>/ (Retrieve)
- PUT /api/admin/users/<id>/ (Update)
- PATCH /api/admin/users/<id>/ (Partial update)
- DELETE /api/admin/users/<id>/ (Delete)
"""

import pytest
from django.core import mail
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User, UserRole

USERS_URL = "/api/admin/users/"


def get_auth_client(api_client, user):
    refresh = RefreshToken.for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    api_client._user = user
    return api_client


@pytest.mark.django_db
class TestAdminUserCreation:
    """Test POST /api/admin/users/"""

    def test_super_admin_cannot_create_firm_admin(self, api_client, super_admin):
        client = get_auth_client(api_client, super_admin)
        payload = {
            "name": "Jane Firm Admin",
            "email": "jane.firmadmin@example.com",
            "phone": "+1234567890",
            "address": "123 Main St",
            "role": UserRole.FIRM_ADMIN,
        }
        response = client.post(USERS_URL, payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "law firm admin" in response.data.get("error", "").lower()

    def test_super_admin_create_super_admin_success(self, api_client, super_admin):
        client = get_auth_client(api_client, super_admin)
        payload = {
            "name": "Second Super Admin",
            "email": "second.super@example.com",
            "role": UserRole.SUPER_ADMIN,
        }
        response = client.post(USERS_URL, payload)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["role"] == UserRole.SUPER_ADMIN
        assert response.data["is_superuser"] is True
        assert response.data["is_staff"] is True

        # Verify welcome email was sent
        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == ["second.super@example.com"]
        assert "Your Law Firm Account Has Been Created" in mail.outbox[0].subject
        assert "Temporary Password:" in mail.outbox[0].body

    def test_super_admin_cannot_create_lawyer_role(self, api_client, super_admin):
        client = get_auth_client(api_client, super_admin)
        payload = {
            "name": "Test Lawyer",
            "email": "lawyer123@example.com",
            "role": UserRole.LAWYER,
        }
        response = client.post(USERS_URL, payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "role" in response.data.get("error", response.data)

    def test_super_admin_cannot_create_clerk_role(self, api_client, super_admin):
        client = get_auth_client(api_client, super_admin)
        payload = {
            "name": "Test Clerk",
            "email": "clerk123@example.com",
            "role": UserRole.CLERK,
        }
        response = client.post(USERS_URL, payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "role" in response.data.get("error", response.data)

    def test_firm_admin_cannot_create_user(self, api_client, firm_admin):
        client = get_auth_client(api_client, firm_admin)
        payload = {
            "name": "Another User",
            "email": "another.user@example.com",
            "role": UserRole.FIRM_ADMIN,
        }
        response = client.post(USERS_URL, payload)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_firm_admin_can_still_list_users(self, api_client, firm_admin, make_user):
        make_user(email="other.user@example.com", role=UserRole.FIRM_ADMIN)
        client = get_auth_client(api_client, firm_admin)
        response = client.get(USERS_URL)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] >= 1

    def test_create_user_duplicate_email_fails(self, api_client, super_admin, make_user):
        make_user(email="existing@example.com")
        client = get_auth_client(api_client, super_admin)
        payload = {
            "name": "Duplicate User",
            "email": "EXISTING@example.com",
            "role": UserRole.SUPER_ADMIN,
        }
        response = client.post(USERS_URL, payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "email" in response.data.get("error", response.data)

    def test_lawyer_cannot_create_user(self, api_client, lawyer):
        client = get_auth_client(api_client, lawyer)
        payload = {
            "name": "Unauthorized",
            "email": "unauth@example.com",
            "role": UserRole.SUPER_ADMIN,
        }
        response = client.post(USERS_URL, payload)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_cannot_create_user(self, api_client):
        payload = {
            "name": "Anon",
            "email": "anon@example.com",
            "role": UserRole.FIRM_ADMIN,
        }
        response = api_client.post(USERS_URL, payload)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestAdminUserList:
    """Test GET /api/admin/users/"""

    def test_list_users_excludes_requesting_user(self, api_client, super_admin, make_user):
        u1 = make_user(email="u1@example.com", name="User One")
        u2 = make_user(email="u2@example.com", name="User Two")

        client = get_auth_client(api_client, super_admin)
        response = client.get(USERS_URL)

        assert response.status_code == status.HTTP_200_OK
        emails = [item["email"] for item in response.data["results"]]
        assert super_admin.email not in emails
        assert u1.email in emails
        assert u2.email in emails

    def test_list_users_pagination(self, api_client, super_admin, make_user):
        for i in range(25):
            make_user(email=f"user{i}@example.com", name=f"User {i}")

        client = get_auth_client(api_client, super_admin)
        response = client.get(f"{USERS_URL}?page=1&page_size=10")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 25
        assert len(response.data["results"]) == 10
        assert response.data["total_pages"] == 3
        assert response.data["current_page"] == 1
        assert response.data["next"] is not None
        assert response.data["previous"] is None

    def test_list_users_search(self, api_client, super_admin, make_user):
        make_user(email="alice.smith@example.com", name="Alice Smith", phone="111222333")
        make_user(email="bob.jones@example.com", name="Bob Jones", phone="444555666")
        make_user(email="charlie@example.com", name="Charlie Brown", phone="999888777")

        client = get_auth_client(api_client, super_admin)

        # Search by name
        res = client.get(f"{USERS_URL}?search=Alice")
        assert res.data["count"] == 1
        assert res.data["results"][0]["name"] == "Alice Smith"

        # Search by email
        res = client.get(f"{USERS_URL}?search=bob.jones")
        assert res.data["count"] == 1
        assert res.data["results"][0]["email"] == "bob.jones@example.com"

        # Search by phone
        res = client.get(f"{USERS_URL}?search=999888")
        assert res.data["count"] == 1
        assert res.data["results"][0]["name"] == "Charlie Brown"

    def test_list_users_filter_role_and_is_active(self, api_client, super_admin, make_user):
        make_user(email="fa@example.com", role=UserRole.FIRM_ADMIN, is_active=True)
        make_user(email="lw1@example.com", role=UserRole.LAWYER, is_active=True)
        make_user(email="lw2@example.com", role=UserRole.LAWYER, is_active=False)

        client = get_auth_client(api_client, super_admin)

        # Filter by role
        res = client.get(f"{USERS_URL}?role={UserRole.LAWYER}")
        assert res.data["count"] == 2

        # Filter by role and is_active
        res = client.get(f"{USERS_URL}?role={UserRole.LAWYER}&is_active=true")
        assert res.data["count"] == 1
        assert res.data["results"][0]["email"] == "lw1@example.com"

    def test_non_admin_cannot_list_users(self, api_client, lawyer):
        client = get_auth_client(api_client, lawyer)
        response = client.get(USERS_URL)
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestAdminUserDetailUpdateDelete:
    """Test GET/PUT/PATCH/DELETE /api/admin/users/<id>/"""

    def test_retrieve_user_detail(self, api_client, super_admin, make_user):
        target = make_user(email="target@example.com", name="Target User", phone="12345")
        client = get_auth_client(api_client, super_admin)

        response = client.get(f"{USERS_URL}{target.id}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == target.id
        assert response.data["name"] == "Target User"
        assert response.data["email"] == "target@example.com"

    def test_update_user_put(self, api_client, super_admin, make_user):
        target = make_user(email="target@example.com", name="Target User")
        client = get_auth_client(api_client, super_admin)

        payload = {
            "name": "Updated Target",
            "phone": "9876543210",
            "address": "456 Oak St",
            "role": UserRole.LAWYER,
            "is_active": True,
        }
        response = client.put(f"{USERS_URL}{target.id}/", payload)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == "Updated Target"
        assert response.data["role"] == UserRole.LAWYER

        target.refresh_from_db()
        assert target.name == "Updated Target"
        assert target.role == UserRole.LAWYER

    def test_partial_update_user_patch(self, api_client, super_admin, make_user):
        target = make_user(email="target@example.com", name="Target User", is_active=True)
        client = get_auth_client(api_client, super_admin)

        response = client.patch(f"{USERS_URL}{target.id}/", {"is_active": False})
        assert response.status_code == status.HTTP_200_OK
        assert response.data["is_active"] is False

        target.refresh_from_db()
        assert target.is_active is False

    def test_delete_user_success(self, api_client, super_admin, make_user):
        target = make_user(email="delete_me@example.com")
        client = get_auth_client(api_client, super_admin)

        response = client.delete(f"{USERS_URL}{target.id}/")
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not User.objects.filter(id=target.id).exists()

    def test_cannot_delete_self(self, api_client, super_admin):
        client = get_auth_client(api_client, super_admin)
        response = client.delete(f"{USERS_URL}{super_admin.id}/")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_firm_admin_cannot_delete_super_admin(self, api_client, firm_admin, super_admin):
        client = get_auth_client(api_client, firm_admin)
        response = client.delete(f"{USERS_URL}{super_admin.id}/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_firm_admin_cannot_edit_super_admin(self, api_client, firm_admin, super_admin):
        client = get_auth_client(api_client, firm_admin)
        response = client.patch(f"{USERS_URL}{super_admin.id}/", {"name": "Hacked Name"})
        assert response.status_code == status.HTTP_403_FORBIDDEN
