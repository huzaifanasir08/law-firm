"""
Tests for Task model and Lawyer Task CRUD, auto-timestamps, and permissions.
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
    return Firm.objects.create(name="Apex Law Partners", type=FirmType.MULTI, email="contact@apexlaw.com")


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
def lawyer_user(make_user, test_firm):
    lawyer = make_user(email="harvey@apexlaw.com", name="Harvey Specter", role=UserRole.LAWYER)
    lawyer.firm = test_firm
    lawyer.save(update_fields=["firm"])
    return lawyer


@pytest.fixture
def other_lawyer(make_user, test_firm):
    lawyer = make_user(email="mike@apexlaw.com", name="Mike Ross", role=UserRole.LAWYER)
    lawyer.firm = test_firm
    lawyer.save(update_fields=["firm"])
    return lawyer


@pytest.fixture
def clerk_user(make_user, test_firm, lawyer_user):
    clerk = make_user(email="rachel@apexlaw.com", name="Rachel Zane", role=UserRole.CLERK)
    clerk.firm = test_firm
    clerk.lawyer = lawyer_user
    clerk.save(update_fields=["firm", "lawyer"])
    return clerk


@pytest.mark.django_db
class TestLawyerTaskManagement:
    """Test suite for lawyer task CRUD and lifecycle timestamps."""

    def test_create_task_pending_without_clerk(self, lawyer_user):
        client = get_auth_client(lawyer_user)
        payload = {
            "name": "Draft Contract",
            "desc": "Prepare initial NDA draft for merger.",
        }
        response = client.post("/api/lawyer/tasks/", payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        data = response.data

        assert data["name"] == "Draft Contract"
        assert data["desc"] == "Prepare initial NDA draft for merger."
        assert data["status"] == TaskStatus.PENDING
        assert data["lawyer_id"] == lawyer_user.id
        assert data["clerk_id"] is None
        assert data["assigned_at"] is None
        assert data["started_at"] is None
        assert data["completed_at"] is None
        assert data["canceled_at"] is None

    def test_create_task_with_clerk_auto_transitions_to_assigned(self, lawyer_user, clerk_user):
        client = get_auth_client(lawyer_user)
        payload = {
            "name": "File Motion to Dismiss",
            "desc": "File paperwork at district court.",
            "clerk": clerk_user.id,
        }
        response = client.post("/api/lawyer/tasks/", payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        data = response.data

        assert data["name"] == "File Motion to Dismiss"
        assert data["status"] == TaskStatus.ASSIGNED
        assert data["clerk_id"] == clerk_user.id
        assert data["assigned_at"] is not None

    def test_task_status_transitions_auto_set_timestamps(self, lawyer_user, clerk_user):
        task = Task.objects.create(
            name="Research Case Law",
            desc="Look into precedents for IP infringement.",
            lawyer=lawyer_user,
            clerk=clerk_user,
            status=TaskStatus.ASSIGNED,
        )
        assert task.assigned_at is not None
        assert task.started_at is None
        assert task.completed_at is None

        client = get_auth_client(lawyer_user)

        # Transition to STARTED
        patch1 = client.patch(f"/api/lawyer/tasks/{task.id}/", {"status": "STARTED"}, format="json")
        assert patch1.status_code == status.HTTP_200_OK
        assert patch1.data["status"] == TaskStatus.STARTED
        assert patch1.data["started_at"] is not None

        # Transition to COMPLETED
        patch2 = client.patch(f"/api/lawyer/tasks/{task.id}/", {"status": "COMPLETED"}, format="json")
        assert patch2.status_code == status.HTTP_200_OK
        assert patch2.data["status"] == TaskStatus.COMPLETED
        assert patch2.data["completed_at"] is not None

    def test_task_status_canceled_sets_canceled_at(self, lawyer_user):
        task = Task.objects.create(
            name="Cancelled Deposition",
            desc="Witness unavailable.",
            lawyer=lawyer_user,
            status=TaskStatus.PENDING,
        )
        client = get_auth_client(lawyer_user)
        patch = client.patch(f"/api/lawyer/tasks/{task.id}/", {"status": "CANCELED"}, format="json")
        assert patch.status_code == status.HTTP_200_OK
        assert patch.data["status"] == TaskStatus.CANCELED
        assert patch.data["canceled_at"] is not None
        assert patch.data["cenceled_at"] is not None

    def test_task_status_cenceld_spelling_accepted(self, lawyer_user):
        task = Task.objects.create(
            name="Another Task",
            lawyer=lawyer_user,
            status=TaskStatus.PENDING,
        )
        client = get_auth_client(lawyer_user)
        patch = client.patch(f"/api/lawyer/tasks/{task.id}/", {"status": "cenceld"}, format="json")
        assert patch.status_code == status.HTTP_200_OK
        assert patch.data["status"] == TaskStatus.CANCELED
        assert patch.data["canceled_at"] is not None

    def test_list_tasks_scoped_to_lawyer_with_filters(self, lawyer_user, other_lawyer, clerk_user):
        t1 = Task.objects.create(name="Task One", lawyer=lawyer_user, clerk=clerk_user, status=TaskStatus.ASSIGNED)
        t2 = Task.objects.create(name="Task Two", lawyer=lawyer_user, status=TaskStatus.PENDING)
        Task.objects.create(name="Other Lawyer Task", lawyer=other_lawyer, status=TaskStatus.PENDING)

        client = get_auth_client(lawyer_user)
        response = client.get("/api/lawyer/tasks/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2

        # Filter by status
        resp_filter = client.get(f"/api/lawyer/tasks/?status={TaskStatus.ASSIGNED}")
        assert resp_filter.status_code == status.HTTP_200_OK
        assert resp_filter.data["count"] == 1
        assert resp_filter.data["results"][0]["name"] == "Task One"

        # Filter by clerk
        resp_clerk = client.get(f"/api/lawyer/tasks/?clerk={clerk_user.id}")
        assert resp_clerk.status_code == status.HTTP_200_OK
        assert resp_clerk.data["count"] == 1

    def test_retrieve_and_delete_task(self, lawyer_user):
        task = Task.objects.create(name="Task To Delete", lawyer=lawyer_user)
        client = get_auth_client(lawyer_user)

        # Retrieve
        det = client.get(f"/api/lawyer/tasks/{task.id}/")
        assert det.status_code == status.HTTP_200_OK
        assert det.data["name"] == "Task To Delete"

        # Delete
        delete_resp = client.delete(f"/api/lawyer/tasks/{task.id}/")
        assert delete_resp.status_code == status.HTTP_204_NO_CONTENT
        assert not Task.objects.filter(id=task.id).exists()

    def test_individual_firm_admin_can_manage_tasks(self, individual_firm_admin, individual_firm, make_user):
        clerk = make_user(email="solo_clerk@law.com", role=UserRole.CLERK, firm=individual_firm)
        client = get_auth_client(individual_firm_admin)

        # Create
        create_resp = client.post(
            "/api/lawyer/tasks/",
            {"name": "Solo Task 1", "desc": "Do research", "clerk": clerk.id},
            format="json",
        )
        assert create_resp.status_code == status.HTTP_201_CREATED
        task_id = create_resp.data["id"]

        # List
        list_resp = client.get("/api/lawyer/tasks/")
        assert list_resp.status_code == status.HTTP_200_OK
        assert list_resp.data["count"] == 1

        # Update
        patch_resp = client.patch(f"/api/lawyer/tasks/{task_id}/", {"name": "Updated Solo Task"})
        assert patch_resp.status_code == status.HTTP_200_OK
        assert patch_resp.data["name"] == "Updated Solo Task"

        # Delete
        del_resp = client.delete(f"/api/lawyer/tasks/{task_id}/")
        assert del_resp.status_code == status.HTTP_204_NO_CONTENT
