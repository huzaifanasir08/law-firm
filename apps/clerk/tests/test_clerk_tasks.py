"""
Tests for Clerk Task viewing, lifecycle status updates, profile, and permissions.
"""

import pytest
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User, UserRole
from apps.firm.models import Firm, FirmType
from apps.lawyer.models import Task, TaskStatus


def get_auth_client(user: User) -> APIClient:
    """Helper to return an authenticated API client for a given user."""
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    client._user = user
    return client


@pytest.fixture
def test_firm(db):
    return Firm.objects.create(name="Apex Law Partners", type=FirmType.MULTI, email="apex@law.com")


@pytest.fixture
def lawyer_user(make_user, test_firm):
    lawyer = make_user(email="harvey@apexlaw.com", name="Harvey Specter", role=UserRole.LAWYER)
    lawyer.firm = test_firm
    lawyer.save(update_fields=["firm"])
    return lawyer


@pytest.fixture
def clerk_user(make_user, test_firm, lawyer_user):
    clerk = make_user(email="clerk1@apexlaw.com", name="Clerk One", role=UserRole.CLERK)
    clerk.firm = test_firm
    clerk.lawyer = lawyer_user
    clerk.save(update_fields=["firm", "lawyer"])
    return clerk


@pytest.fixture
def other_clerk(make_user, test_firm, lawyer_user):
    clerk = make_user(email="clerk2@apexlaw.com", name="Clerk Two", role=UserRole.CLERK)
    clerk.firm = test_firm
    clerk.lawyer = lawyer_user
    clerk.save(update_fields=["firm", "lawyer"])
    return clerk


@pytest.mark.django_db
class TestClerkTasksAndProfile:
    """Test suite for clerk task operations and profile."""

    def test_clerk_list_only_assigned_tasks(self, clerk_user, other_clerk, lawyer_user):
        t1 = Task.objects.create(name="Task for Clerk 1", lawyer=lawyer_user, clerk=clerk_user, status=TaskStatus.ASSIGNED)
        t2 = Task.objects.create(name="Another for Clerk 1", lawyer=lawyer_user, clerk=clerk_user, status=TaskStatus.ASSIGNED)
        Task.objects.create(name="Task for Clerk 2", lawyer=lawyer_user, clerk=other_clerk, status=TaskStatus.ASSIGNED)
        Task.objects.create(name="Unassigned Task", lawyer=lawyer_user, status=TaskStatus.PENDING)

        client = get_auth_client(clerk_user)
        response = client.get("/api/clerk/tasks/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2
        names = [item["name"] for item in response.data["results"]]
        assert "Task for Clerk 1" in names
        assert "Another for Clerk 1" in names
        assert "Task for Clerk 2" not in names

    def test_clerk_retrieve_task_detail(self, clerk_user, lawyer_user):
        task = Task.objects.create(
            name="Research Case Precedents",
            desc="Examine antitrust cases from 2020-2025.",
            lawyer=lawyer_user,
            clerk=clerk_user,
            status=TaskStatus.ASSIGNED,
        )
        client = get_auth_client(clerk_user)
        response = client.get(f"/api/clerk/tasks/{task.id}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == "Research Case Precedents"
        assert response.data["desc"] == "Examine antitrust cases from 2020-2025."
        assert response.data["clerk_id"] == clerk_user.id
        assert response.data["lawyer_name"] == lawyer_user.name

    def test_clerk_cannot_retrieve_other_clerks_task(self, clerk_user, other_clerk, lawyer_user):
        task = Task.objects.create(
            name="Confidential Task",
            lawyer=lawyer_user,
            clerk=other_clerk,
            status=TaskStatus.ASSIGNED,
        )
        client = get_auth_client(clerk_user)
        response = client.get(f"/api/clerk/tasks/{task.id}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_clerk_update_task_status_lifecycle(self, clerk_user, lawyer_user):
        task = Task.objects.create(
            name="Court Filing",
            desc="Submit signed documents.",
            lawyer=lawyer_user,
            clerk=clerk_user,
            status=TaskStatus.ASSIGNED,
        )
        client = get_auth_client(clerk_user)

        # Update to STARTED via detail endpoint
        patch1 = client.patch(f"/api/clerk/tasks/{task.id}/", {"status": "STARTED"}, format="json")
        assert patch1.status_code == status.HTTP_200_OK
        assert patch1.data["status"] == TaskStatus.STARTED
        assert patch1.data["started_at"] is not None

        # Update to COMPLETED via dedicated status endpoint
        patch2 = client.patch(f"/api/clerk/tasks/{task.id}/status/", {"status": "COMPLETED"}, format="json")
        assert patch2.status_code == status.HTTP_200_OK
        assert patch2.data["status"] == TaskStatus.COMPLETED
        assert patch2.data["completed_at"] is not None

    def test_clerk_profile_view(self, clerk_user, lawyer_user, test_firm):
        client = get_auth_client(clerk_user)
        response = client.get("/api/clerk/profile/")
        assert response.status_code == status.HTTP_200_OK
        data = response.data
        assert data["email"] == clerk_user.email
        assert data["name"] == clerk_user.name
        assert data["role"] == UserRole.CLERK
        assert data["firm_name"] == test_firm.name
        assert data["lawyer_name"] == lawyer_user.name

    def test_lawyer_cannot_access_clerk_endpoints(self, lawyer_user):
        client = get_auth_client(lawyer_user)
        response = client.get("/api/clerk/tasks/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_cannot_access_clerk_endpoints(self):
        client = APIClient()
        response = client.get("/api/clerk/tasks/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
