"""
Tests for Firm-level Clerk management (onboarding, credentials email, soft-delete, permissions).
"""

import pytest
from django.core import mail
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User, UserRole
from apps.firm.models import Firm, FirmType


def get_auth_client(user: User) -> APIClient:
    """Helper to return an authenticated API client for a given user."""
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    client._user = user
    return client


@pytest.fixture
def individual_firm(db):
    return Firm.objects.create(name="Solo Law Practice", type=FirmType.INDIVIDUAL, email="solo@law.com")


@pytest.fixture
def individual_firm_admin(make_user, individual_firm):
    admin = make_user(email="solo_admin@law.com", name="Solo Admin", role=UserRole.FIRM_ADMIN)
    admin.firm = individual_firm
    admin.save(update_fields=["firm"])
    return admin


@pytest.fixture
def multi_firm(db):
    return Firm.objects.create(name="Apex Law Partners", type=FirmType.MULTI, email="apex@law.com")


@pytest.fixture
def multi_firm_admin(make_user, multi_firm):
    admin = make_user(email="multi_admin@apex.com", name="Multi Admin", role=UserRole.FIRM_ADMIN)
    admin.firm = multi_firm
    admin.save(update_fields=["firm"])
    return admin


@pytest.mark.django_db
class TestFirmClerkManagement:
    """Test suite for managing clerks at the firm level."""

    def test_individual_firm_add_clerk_success_and_sends_email(self, individual_firm_admin, individual_firm):
        client = get_auth_client(individual_firm_admin)
        payload = {
            "name": "Alex Clerk",
            "email": "alex.clerk@law.com",
            "phone": "+1987654321",
            "address": "456 Court Ave",
        }

        response = client.post("/api/firm/clerks/", payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        data = response.data

        assert data["name"] == "Alex Clerk"
        assert data["email"] == "alex.clerk@law.com"
        assert data["role"] == UserRole.CLERK
        assert data["firm_id"] == individual_firm.id
        assert data["is_active"] is True

        # Verify clerk exists in database
        clerk = User.objects.get(email="alex.clerk@law.com")
        assert clerk.role == UserRole.CLERK
        assert clerk.firm == individual_firm
        assert clerk.is_active is True
        assert clerk.has_usable_password()

        # Verify welcome credentials email was sent
        assert len(mail.outbox) == 1
        sent_email = mail.outbox[0]
        assert sent_email.to == ["alex.clerk@law.com"]
        assert "Welcome to Solo Law Practice" in sent_email.subject
        assert "Temporary Password:" in sent_email.body

    def test_individual_firm_add_clerk_duplicate_email_fails(self, individual_firm_admin, make_user):
        make_user(email="existing_clerk@law.com")
        client = get_auth_client(individual_firm_admin)
        payload = {
            "name": "Duplicate Clerk",
            "email": "existing_clerk@law.com",
        }
        response = client.post("/api/firm/clerks/", payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "email" in response.data.get("error", response.data)

    def test_individual_firm_list_clerks(self, individual_firm_admin, individual_firm, make_user):
        make_user(email="c1@law.com", name="Clerk One", role=UserRole.CLERK, firm=individual_firm)
        make_user(email="c2@law.com", name="Clerk Two", role=UserRole.CLERK, firm=individual_firm)

        client = get_auth_client(individual_firm_admin)
        response = client.get("/api/firm/clerks/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2

    def test_individual_firm_retrieve_update_soft_delete_and_reactivate_clerk(
        self, individual_firm_admin, individual_firm, make_user
    ):
        clerk = make_user(email="manage_c@law.com", name="Manageable Clerk", role=UserRole.CLERK, firm=individual_firm)
        client = get_auth_client(individual_firm_admin)

        # Retrieve
        det_resp = client.get(f"/api/firm/clerks/{clerk.id}/")
        assert det_resp.status_code == status.HTTP_200_OK
        assert det_resp.data["name"] == "Manageable Clerk"

        # Update
        patch_resp = client.patch(f"/api/firm/clerks/{clerk.id}/", {"name": "Updated Clerk Name"})
        assert patch_resp.status_code == status.HTTP_200_OK
        assert patch_resp.data["name"] == "Updated Clerk Name"

        # Soft delete
        del_resp = client.delete(f"/api/firm/clerks/{clerk.id}/")
        assert del_resp.status_code == status.HTTP_200_OK
        clerk.refresh_from_db()
        assert clerk.is_active is False

        # Reactivate
        react_resp = client.post(f"/api/firm/clerks/{clerk.id}/reactivate/")
        assert react_resp.status_code == status.HTTP_200_OK
        clerk.refresh_from_db()
        assert clerk.is_active is True

    def test_multi_firm_and_super_admin_cannot_access_firm_clerks(
        self, multi_firm_admin, multi_firm, super_admin, individual_firm, make_user
    ):
        clerk = make_user(email="solo_clerk@law.com", role=UserRole.CLERK, firm=individual_firm)

        # Multi firm admin is forbidden from listing, creating, and managing
        multi_client = get_auth_client(multi_firm_admin)
        assert multi_client.get("/api/firm/clerks/").status_code == status.HTTP_403_FORBIDDEN
        assert multi_client.post("/api/firm/clerks/", {"name": "New Clerk", "email": "new.clerk@law.com"}).status_code == status.HTTP_403_FORBIDDEN
        assert multi_client.get(f"/api/firm/clerks/{clerk.id}/").status_code == status.HTTP_403_FORBIDDEN

        # Super admin is also forbidden - clerk management is strictly scoped to INDIVIDUAL firm admin
        super_client = get_auth_client(super_admin)
        assert super_client.get("/api/firm/clerks/").status_code == status.HTTP_403_FORBIDDEN
        assert super_client.post("/api/firm/clerks/", {"name": "New Clerk 2", "email": "new.clerk2@law.com"}).status_code == status.HTTP_403_FORBIDDEN
        assert super_client.get(f"/api/firm/clerks/{clerk.id}/").status_code == status.HTTP_403_FORBIDDEN

