"""
Tests for Lawyer Clerk management (onboarding, welcome emails, listing own clerks, isolation).
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
def firm_a(db):
    return Firm.objects.create(name="Firm Alpha", type=FirmType.MULTI, email="alpha@law.com")


@pytest.fixture
def firm_b(db):
    return Firm.objects.create(name="Firm Beta", type=FirmType.MULTI, email="beta@law.com")


@pytest.fixture
def lawyer_a1(make_user, firm_a):
    lawyer = make_user(email="lawyer_a1@alpha.com", name="Lawyer A1", role=UserRole.LAWYER)
    lawyer.firm = firm_a
    lawyer.save(update_fields=["firm"])
    return lawyer


@pytest.fixture
def lawyer_a2(make_user, firm_a):
    lawyer = make_user(email="lawyer_a2@alpha.com", name="Lawyer A2", role=UserRole.LAWYER)
    lawyer.firm = firm_a
    lawyer.save(update_fields=["firm"])
    return lawyer


@pytest.fixture
def lawyer_b(make_user, firm_b):
    lawyer = make_user(email="lawyer_b@beta.com", name="Lawyer B", role=UserRole.LAWYER)
    lawyer.firm = firm_b
    lawyer.save(update_fields=["firm"])
    return lawyer


@pytest.mark.django_db
class TestLawyerClerkManagement:
    """Test suite for lawyer clerk onboarding and management."""

    def test_lawyer_create_clerk_success_and_sends_email(self, lawyer_a1, firm_a):
        client = get_auth_client(lawyer_a1)
        payload = {
            "name": "Donna Paulsen",
            "email": "donna@alpha.com",
            "phone": "+1555123456",
            "address": "601 Lexington Ave",
        }
        response = client.post("/api/lawyer/clerks/", payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        data = response.data

        assert data["name"] == "Donna Paulsen"
        assert data["email"] == "donna@alpha.com"
        assert data["role"] == UserRole.CLERK
        assert data["lawyer_id"] == lawyer_a1.id
        assert data["firm_id"] == firm_a.id
        assert data["is_active"] is True

        # Verify DB record
        clerk = User.objects.get(email="donna@alpha.com")
        assert clerk.role == UserRole.CLERK
        assert clerk.lawyer == lawyer_a1
        assert clerk.firm == firm_a
        assert clerk.has_usable_password()

        # Verify welcome email was sent
        assert len(mail.outbox) == 1
        sent_email = mail.outbox[0]
        assert sent_email.to == ["donna@alpha.com"]
        assert "Welcome to Firm Alpha" in sent_email.subject
        assert "Temporary Password:" in sent_email.body

    def test_lawyer_list_own_clerks(self, lawyer_a1, lawyer_a2, firm_a, make_user):
        # Clerk assigned to lawyer A1
        c1 = make_user(email="c1@alpha.com", name="Clerk 1", role=UserRole.CLERK, firm=firm_a)
        c1.lawyer = lawyer_a1
        c1.save(update_fields=["lawyer"])

        # Clerk assigned to lawyer A2
        c2 = make_user(email="c2@alpha.com", name="Clerk 2", role=UserRole.CLERK, firm=firm_a)
        c2.lawyer = lawyer_a2
        c2.save(update_fields=["lawyer"])

        client = get_auth_client(lawyer_a1)

        # General list returns firm clerks
        resp = client.get("/api/lawyer/clerks/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["count"] == 2

        # only_own filter returns only lawyer_a1's clerks
        resp_own = client.get("/api/lawyer/clerks/?only_own=true")
        assert resp_own.status_code == status.HTTP_200_OK
        assert resp_own.data["count"] == 1
        assert resp_own.data["results"][0]["email"] == "c1@alpha.com"

    def test_lawyer_retrieve_update_and_soft_delete_clerk(self, lawyer_a1, firm_a, make_user):
        clerk = make_user(email="c_manage@alpha.com", name="Clerk Manage", role=UserRole.CLERK, firm=firm_a)
        clerk.lawyer = lawyer_a1
        clerk.save(update_fields=["lawyer"])

        client = get_auth_client(lawyer_a1)

        # Retrieve
        det = client.get(f"/api/lawyer/clerks/{clerk.id}/")
        assert det.status_code == status.HTTP_200_OK
        assert det.data["name"] == "Clerk Manage"

        # Update
        patch = client.patch(f"/api/lawyer/clerks/{clerk.id}/", {"name": "Clerk Manage Updated"})
        assert patch.status_code == status.HTTP_200_OK
        assert patch.data["name"] == "Clerk Manage Updated"

        # Soft delete
        delete_resp = client.delete(f"/api/lawyer/clerks/{clerk.id}/")
        assert delete_resp.status_code == status.HTTP_200_OK
        clerk.refresh_from_db()
        assert clerk.is_active is False

        # Reactivate
        react_resp = client.post(f"/api/lawyer/clerks/{clerk.id}/reactivate/")
        assert react_resp.status_code == status.HTTP_200_OK
        clerk.refresh_from_db()
        assert clerk.is_active is True

    def test_lawyer_cannot_access_or_manage_other_firm_clerk(self, lawyer_a1, lawyer_b, firm_b, make_user):
        other_clerk = make_user(email="c_b@beta.com", role=UserRole.CLERK, firm=firm_b)
        other_clerk.lawyer = lawyer_b
        other_clerk.save(update_fields=["lawyer"])

        client = get_auth_client(lawyer_a1)
        response = client.get(f"/api/lawyer/clerks/{other_clerk.id}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_super_admin_and_multi_firm_cannot_access_lawyer_clerks(
        self, super_admin, firm_a, make_user
    ):
        multi_admin = make_user(email="multi_admin@alpha.com", role=UserRole.FIRM_ADMIN, firm=firm_a)
        clerk = make_user(email="clerk_x@alpha.com", role=UserRole.CLERK, firm=firm_a)

        # Super admin cannot list or create via lawyer clerks endpoint
        super_client = get_auth_client(super_admin)
        assert super_client.get("/api/lawyer/clerks/").status_code == status.HTTP_403_FORBIDDEN
        assert super_client.post("/api/lawyer/clerks/", {"name": "Test", "email": "test@test.com"}).status_code == status.HTTP_403_FORBIDDEN
        assert super_client.get(f"/api/lawyer/clerks/{clerk.id}/").status_code == status.HTTP_403_FORBIDDEN

        # Multi firm admin cannot list or create via lawyer clerks endpoint
        multi_client = get_auth_client(multi_admin)
        assert multi_client.get("/api/lawyer/clerks/").status_code == status.HTTP_403_FORBIDDEN
        assert multi_client.post("/api/lawyer/clerks/", {"name": "Test", "email": "test@test.com"}).status_code == status.HTTP_403_FORBIDDEN
        assert multi_client.get(f"/api/lawyer/clerks/{clerk.id}/").status_code == status.HTTP_403_FORBIDDEN

