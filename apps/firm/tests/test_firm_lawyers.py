"""
Tests for Firm management, lawyer onboarding, soft deletion, and firm stats.
"""

import pytest
from django.core import mail
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User, UserRole
from apps.firm.models import Firm
from apps.matters.models import Matter, MatterStatus
from apps.lawyer.models import Client


def get_auth_client(user: User) -> APIClient:
    """Helper to return an authenticated API client for a given user."""
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    client._user = user
    return client


@pytest.fixture
def test_firm(db):
    return Firm.objects.create(name="Apex Law Partners", email="contact@apexlaw.com")


@pytest.fixture
def firm_admin_user(make_user, test_firm):
    admin = make_user(email="admin@apexlaw.com", name="Apex Admin", role=UserRole.FIRM_ADMIN)
    admin.firm = test_firm
    admin.save(update_fields=["firm"])
    return admin


@pytest.fixture
def other_firm(db):
    return Firm.objects.create(name="Lexicon Legal", email="contact@lexicon.com")


@pytest.fixture
def other_firm_admin(make_user, other_firm):
    admin = make_user(email="admin@lexicon.com", name="Lexicon Admin", role=UserRole.FIRM_ADMIN)
    admin.firm = other_firm
    admin.save(update_fields=["firm"])
    return admin


@pytest.mark.django_db
class TestFirmLawyerOnboarding:
    """Test suite for adding lawyers via firm app."""

    def test_add_lawyer_success(self, firm_admin_user, test_firm):
        client = get_auth_client(firm_admin_user)
        payload = {
            "name": "Jane Lawyer",
            "email": "jane@apexlaw.com",
            "phone": "+1234567890",
            "address": "123 Legal Way",
        }

        response = client.post("/api/firm/lawyers/", payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        data = response.data

        assert data["name"] == "Jane Lawyer"
        assert data["email"] == "jane@apexlaw.com"
        assert data["role"] == UserRole.LAWYER
        assert data["firm_id"] == test_firm.id
        assert data["firm_name"] == test_firm.name
        assert data["is_active"] is True

        # Verify lawyer exists in database
        lawyer = User.objects.get(email="jane@apexlaw.com")
        assert lawyer.role == UserRole.LAWYER
        assert lawyer.firm == test_firm
        assert lawyer.is_active is True
        assert lawyer.has_usable_password()

        # Verify welcome email was sent
        assert len(mail.outbox) == 1
        sent_email = mail.outbox[0]
        assert sent_email.to == ["jane@apexlaw.com"]
        assert "Welcome to Apex Law Partners" in sent_email.subject
        assert "Temporary Password:" in sent_email.body

    def test_add_lawyer_duplicate_email_fails(self, firm_admin_user, make_user):
        make_user(email="existing@example.com")
        client = get_auth_client(firm_admin_user)
        payload = {
            "name": "Another Lawyer",
            "email": "existing@example.com",
        }
        response = client.post("/api/firm/lawyers/", payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "email" in response.data.get("error", "")

    def test_lawyer_cannot_onboard_lawyer(self, make_user):
        lawyer = make_user(email="lawyer1@example.com", role=UserRole.LAWYER)
        client = get_auth_client(lawyer)
        payload = {"name": "New Lawyer", "email": "newlawyer@example.com"}
        response = client.post("/api/firm/lawyers/", payload, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_cannot_onboard_lawyer(self):
        client = APIClient()
        payload = {"name": "New Lawyer", "email": "newlawyer@example.com"}
        response = client.post("/api/firm/lawyers/", payload, format="json")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestFirmLawyerManagement:
    """Test suite for listing, updating, soft deleting, and reactivating lawyers."""

    def test_list_lawyers_scoped_to_firm(self, firm_admin_user, other_firm_admin, make_user, test_firm, other_firm):
        # Create 2 lawyers in test_firm
        l1 = make_user(email="l1@apex.com", name="Lawyer One", role=UserRole.LAWYER, firm=test_firm)
        l2 = make_user(email="l2@apex.com", name="Lawyer Two", role=UserRole.LAWYER, firm=test_firm)
        # Create 1 lawyer in other_firm
        l3 = make_user(email="l3@lexicon.com", name="Lawyer Three", role=UserRole.LAWYER, firm=other_firm)

        client = get_auth_client(firm_admin_user)
        response = client.get("/api/firm/lawyers/")
        assert response.status_code == status.HTTP_200_OK

        results = response.data.get("results", response.data)
        ids = [item["id"] for item in results]
        assert l1.id in ids
        assert l2.id in ids
        assert l3.id not in ids

    def test_retrieve_lawyer_detail(self, firm_admin_user, make_user, test_firm):
        lawyer = make_user(email="detail@apex.com", name="Detail Lawyer", role=UserRole.LAWYER, firm=test_firm)
        client = get_auth_client(firm_admin_user)
        response = client.get(f"/api/firm/lawyers/{lawyer.id}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == "Detail Lawyer"
        assert response.data["email"] == "detail@apex.com"

    def test_update_lawyer_patch(self, firm_admin_user, make_user, test_firm):
        lawyer = make_user(email="update@apex.com", name="Original Name", role=UserRole.LAWYER, firm=test_firm)
        client = get_auth_client(firm_admin_user)
        response = client.patch(f"/api/firm/lawyers/{lawyer.id}/", {"name": "Updated Name", "phone": "+987654321"}, format="json")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == "Updated Name"
        assert response.data["phone"] == "+987654321"

        lawyer.refresh_from_db()
        assert lawyer.name == "Updated Name"

    def test_soft_delete_lawyer(self, firm_admin_user, make_user, test_firm):
        lawyer = make_user(email="delete@apex.com", name="To Deactivate", role=UserRole.LAWYER, firm=test_firm, is_active=True)
        # Generate token for lawyer
        refresh = RefreshToken.for_user(lawyer)

        client = get_auth_client(firm_admin_user)
        response = client.delete(f"/api/firm/lawyers/{lawyer.id}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["is_active"] is False

        # Verify lawyer is STILL in database, but marked inactive
        lawyer.refresh_from_db()
        assert lawyer.is_active is False

        # Verify lawyer's refresh token is revoked
        lawyer_client = APIClient()
        token_refresh_res = lawyer_client.post("/api/accounts/refresh/", {"refresh": str(refresh)}, format="json")
        assert token_refresh_res.status_code == status.HTTP_401_UNAUTHORIZED

    def test_reactivate_lawyer(self, firm_admin_user, make_user, test_firm):
        lawyer = make_user(email="reactivate@apex.com", name="To Reactivate", role=UserRole.LAWYER, firm=test_firm, is_active=False)
        client = get_auth_client(firm_admin_user)
        response = client.post(f"/api/firm/lawyers/{lawyer.id}/reactivate/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["is_active"] is True

        lawyer.refresh_from_db()
        assert lawyer.is_active is True

    def test_cannot_manage_other_firm_lawyer(self, firm_admin_user, other_firm_admin, make_user, other_firm):
        other_lawyer = make_user(email="other@lexicon.com", role=UserRole.LAWYER, firm=other_firm)
        client = get_auth_client(firm_admin_user)
        response = client.get(f"/api/firm/lawyers/{other_lawyer.id}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestFirmStats:
    """Test suite for firm-level statistics."""

    def test_firm_stats_counts(self, firm_admin_user, make_user, test_firm):
        # 2 active lawyers, 1 inactive lawyer
        l1 = make_user(email="fa1@apex.com", role=UserRole.LAWYER, firm=test_firm, is_active=True)
        l2 = make_user(email="fa2@apex.com", role=UserRole.LAWYER, firm=test_firm, is_active=True)
        l3 = make_user(email="fa3@apex.com", role=UserRole.LAWYER, firm=test_firm, is_active=False)

        # Create clients
        c1 = Client.objects.create(lawyer=l1, firm=test_firm, name="Client 1")
        c2 = Client.objects.create(lawyer=l2, firm=test_firm, name="Client 2")

        # Create matters across lawyers
        Matter.objects.create(title="Matter 1", lawyer=l1, client=c1, firm=test_firm, status=MatterStatus.OPEN)
        Matter.objects.create(title="Matter 2", lawyer=l1, client=c1, firm=test_firm, status=MatterStatus.CLOSED)
        Matter.objects.create(title="Matter 3", lawyer=l2, client=c2, firm=test_firm, status=MatterStatus.IN_PROGRESS)

        client = get_auth_client(firm_admin_user)
        response = client.get("/api/firm/stats/")
        assert response.status_code == status.HTTP_200_OK

        data = response.data
        assert data["total_lawyers"] == 3
        assert data["active_lawyers"] == 2
        assert data["inactive_lawyers"] == 1
        assert data["total_matters"] == 3
