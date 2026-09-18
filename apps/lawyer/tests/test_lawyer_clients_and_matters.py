"""
Tests for Lawyer client management, matter tracking, and scoped statistics.
"""

from datetime import timedelta
import pytest
from django.core import mail
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User, UserRole
from apps.firm.models import Firm
from apps.lawyer.models import Client
from apps.matters.models import Matter, MatterPriority, MatterStatus


def get_auth_client(user: User) -> APIClient:
    """Helper to return an authenticated API client for a given user."""
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    client._user = user
    return client


@pytest.fixture
def firm(db):
    return Firm.objects.create(name="Sterling & Partners")


@pytest.fixture
def lawyer_user(make_user, firm):
    return make_user(email="harvey@sterling.com", name="Harvey Specter", role=UserRole.LAWYER, firm=firm)


@pytest.fixture
def other_lawyer_user(make_user, firm):
    return make_user(email="mike@sterling.com", name="Mike Ross", role=UserRole.LAWYER, firm=firm)


@pytest.mark.django_db
class TestLawyerClientManagement:
    """Test suite for lawyer client records (system data, no login credentials)."""

    def test_create_client_success(self, lawyer_user, firm):
        client = get_auth_client(lawyer_user)
        payload = {
            "name": "Acme Corp",
            "email": "contact@acme.com",
            "phone": "+1999888777",
            "address": "100 Industrial Parkway",
            "notes": "Key corporate client",
        }

        # Clear mail outbox
        mail.outbox = []

        response = client.post("/api/lawyer/clients/", payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        data = response.data

        assert data["name"] == "Acme Corp"
        assert data["role"] == "CLIENT"
        assert data["is_active"] is True
        assert data["lawyer_id"] == lawyer_user.id
        assert data["firm_id"] == firm.id

        # Crucial requirement: NO login credentials or emails generated for clients
        assert len(mail.outbox) == 0

        # Verify client in DB
        c = Client.objects.get(id=data["id"])
        assert c.lawyer == lawyer_user
        assert c.firm == firm
        assert c.is_active is True

    def test_list_clients_scoped_to_lawyer(self, lawyer_user, other_lawyer_user, firm):
        # Create client for lawyer 1
        c1 = Client.objects.create(lawyer=lawyer_user, firm=firm, name="Harvey's Client")
        # Create client for lawyer 2
        c2 = Client.objects.create(lawyer=other_lawyer_user, firm=firm, name="Mike's Client")

        client = get_auth_client(lawyer_user)
        response = client.get("/api/lawyer/clients/")
        assert response.status_code == status.HTTP_200_OK

        results = response.data.get("results", response.data)
        ids = [item["id"] for item in results]
        assert c1.id in ids
        assert c2.id not in ids

    def test_soft_delete_and_reactivate_client(self, lawyer_user, firm):
        c = Client.objects.create(lawyer=lawyer_user, firm=firm, name="Client To Soft Delete", is_active=True)
        client = get_auth_client(lawyer_user)

        # Soft delete
        del_res = client.delete(f"/api/lawyer/clients/{c.id}/")
        assert del_res.status_code == status.HTTP_200_OK
        assert del_res.data["is_active"] is False

        c.refresh_from_db()
        assert c.is_active is False

        # Reactivate
        react_res = client.post(f"/api/lawyer/clients/{c.id}/reactivate/")
        assert react_res.status_code == status.HTTP_200_OK
        assert react_res.data["is_active"] is True

        c.refresh_from_db()
        assert c.is_active is True

    def test_lawyer_client_stats(self, lawyer_user, other_lawyer_user, firm):
        # Harvey: 2 active clients, 1 inactive client
        c1 = Client.objects.create(lawyer=lawyer_user, firm=firm, name="Active 1", is_active=True)
        c2 = Client.objects.create(lawyer=lawyer_user, firm=firm, name="Active 2", is_active=True)
        c3 = Client.objects.create(lawyer=lawyer_user, firm=firm, name="Inactive 1", is_active=False)

        # Create matters for Harvey's clients
        Matter.objects.create(title="M1", lawyer=lawyer_user, client=c1, firm=firm)
        Matter.objects.create(title="M2", lawyer=lawyer_user, client=c2, firm=firm)

        # Mike's client and matter
        c_mike = Client.objects.create(lawyer=other_lawyer_user, firm=firm, name="Mike's C")
        Matter.objects.create(title="M3", lawyer=other_lawyer_user, client=c_mike, firm=firm)

        client = get_auth_client(lawyer_user)
        response = client.get("/api/lawyer/clients/stats/")
        assert response.status_code == status.HTTP_200_OK

        data = response.data
        assert data["total_clients"] == 3
        assert data["active_clients"] == 2
        assert data["inactive_clients"] == 1
        assert data["total_matters"] == 2  # Only matters for Harvey's clients


@pytest.mark.django_db
class TestLawyerMatterManagement:
    """Test suite for lawyer matter tracking and scoped matter stats."""

    def test_create_matter_success(self, lawyer_user, firm):
        c = Client.objects.create(lawyer=lawyer_user, firm=firm, name="Valid Client")
        client = get_auth_client(lawyer_user)
        payload = {
            "title": "Breach of Contract Defense",
            "description": "Commercial dispute",
            "client": c.id,
            "priority": MatterPriority.HIGH,
            "due_date": (timezone.now() + timedelta(days=14)).date().isoformat(),
        }

        response = client.post("/api/lawyer/matters/", payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        data = response.data

        assert data["title"] == "Breach of Contract Defense"
        assert data["client"] == c.id
        assert data["lawyer_id"] == lawyer_user.id
        assert data["firm_id"] == firm.id
        assert data["status"] == MatterStatus.OPEN
        assert data["priority"] == MatterPriority.HIGH
        assert data["case_number"].startswith("MAT-")

    def test_cannot_assign_matter_to_another_lawyers_client(self, lawyer_user, other_lawyer_user, firm):
        mike_client = Client.objects.create(lawyer=other_lawyer_user, firm=firm, name="Mike's Client")
        client = get_auth_client(lawyer_user)
        payload = {
            "title": "Invalid Assignment",
            "client": mike_client.id,
        }
        response = client.post("/api/lawyer/matters/", payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "client" in response.data.get("error", "")

    def test_list_matters_scoped_to_lawyer(self, lawyer_user, other_lawyer_user, firm):
        c1 = Client.objects.create(lawyer=lawyer_user, firm=firm, name="C1")
        c2 = Client.objects.create(lawyer=other_lawyer_user, firm=firm, name="C2")

        m1 = Matter.objects.create(title="Harvey Matter", lawyer=lawyer_user, client=c1, firm=firm)
        m2 = Matter.objects.create(title="Mike Matter", lawyer=other_lawyer_user, client=c2, firm=firm)

        client = get_auth_client(lawyer_user)
        response = client.get("/api/lawyer/matters/")
        assert response.status_code == status.HTTP_200_OK

        results = response.data.get("results", response.data)
        ids = [item["id"] for item in results]
        assert m1.id in ids
        assert m2.id not in ids

    def test_close_matter_sets_closed_at(self, lawyer_user, firm):
        c = Client.objects.create(lawyer=lawyer_user, firm=firm, name="C")
        matter = Matter.objects.create(title="Open Matter", lawyer=lawyer_user, client=c, firm=firm, status=MatterStatus.OPEN)

        client = get_auth_client(lawyer_user)
        response = client.patch(f"/api/lawyer/matters/{matter.id}/", {"status": MatterStatus.CLOSED}, format="json")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == MatterStatus.CLOSED
        assert response.data["closed_at"] is not None

        matter.refresh_from_db()
        assert matter.status == MatterStatus.CLOSED
        assert matter.closed_at is not None

    def test_matter_stats_breakdown(self, lawyer_user, firm):
        c = Client.objects.create(lawyer=lawyer_user, firm=firm, name="C")
        today = timezone.now().date()

        # 1 OPEN matter (overdue: due 2 days ago)
        Matter.objects.create(
            title="Overdue Matter",
            lawyer=lawyer_user,
            client=c,
            firm=firm,
            status=MatterStatus.OPEN,
            due_date=today - timedelta(days=2),
        )

        # 1 IN_PROGRESS matter (due in 3 days -> upcoming)
        Matter.objects.create(
            title="Upcoming Matter",
            lawyer=lawyer_user,
            client=c,
            firm=firm,
            status=MatterStatus.IN_PROGRESS,
            due_date=today + timedelta(days=3),
        )

        # 1 CLOSED matter (even if past due date, should not count as due)
        Matter.objects.create(
            title="Closed Matter",
            lawyer=lawyer_user,
            client=c,
            firm=firm,
            status=MatterStatus.CLOSED,
            due_date=today - timedelta(days=5),
            closed_at=timezone.now(),
        )

        # 1 PENDING matter (no due date)
        Matter.objects.create(
            title="Pending No Due",
            lawyer=lawyer_user,
            client=c,
            firm=firm,
            status=MatterStatus.PENDING,
        )

        client = get_auth_client(lawyer_user)
        response = client.get("/api/lawyer/matters/stats/")
        assert response.status_code == status.HTTP_200_OK

        data = response.data
        assert data["total_matters"] == 4
        assert data["open_matters"] == 3  # OPEN, IN_PROGRESS, PENDING
        assert data["closed_matters"] == 1
        assert data["due_matters"] == 1  # only Overdue Matter
        assert data["upcoming_matters"] == 1  # only Upcoming Matter

    def test_overview_stats_endpoint(self, lawyer_user, firm):
        c = Client.objects.create(lawyer=lawyer_user, firm=firm, name="C")
        Matter.objects.create(title="M", lawyer=lawyer_user, client=c, firm=firm)

        client = get_auth_client(lawyer_user)
        response = client.get("/api/lawyer/stats/")
        assert response.status_code == status.HTTP_200_OK
        data = response.data

        assert "clients" in data
        assert "matters" in data
        assert data["clients"]["total"] == 1
        assert data["matters"]["total"] == 1
