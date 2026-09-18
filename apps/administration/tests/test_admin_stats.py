"""
Tests for Admin Statistics API:
- GET /api/admin/stats/
"""

from datetime import timedelta
import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import UserRole

STATS_URL = "/api/admin/stats/"


def get_auth_client(api_client, user):
    refresh = RefreshToken.for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    api_client._user = user
    return api_client


@pytest.mark.django_db
class TestAdminStats:
    """Test GET /api/admin/stats/"""

    def test_stats_counts_accurate(self, api_client, super_admin, make_user):
        # Create various users across roles and states
        u1 = make_user(email="fa1@example.com", role=UserRole.FIRM_ADMIN, is_active=True)
        u2 = make_user(email="fa2@example.com", role=UserRole.FIRM_ADMIN, is_active=True)
        u3 = make_user(email="law1@example.com", role=UserRole.LAWYER, is_active=True)
        u4 = make_user(email="law2@example.com", role=UserRole.LAWYER, is_active=False)
        u5 = make_user(email="clerk1@example.com", role=UserRole.CLERK, is_active=True)

        # Mock / adjust created_at for users to simulate last month
        now = timezone.now()
        # Set u5 created_at to last month
        first_day_this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_month_date = first_day_this_month - timedelta(days=15)
        u5.created_at = last_month_date
        u5.save(update_fields=["created_at"])

        client = get_auth_client(api_client, super_admin)
        response = client.get(STATS_URL)

        assert response.status_code == status.HTTP_200_OK

        data = response.data
        # Total users: super_admin + 5 created users = 6
        assert data["total_users"] == 6

        # Active users: super_admin, u1, u2, u3, u5 = 5 (u4 is inactive)
        assert data["total_active_users"] == 5

        # Users this month: super_admin, u1, u2, u3, u4 = 5
        assert data["users_this_month"] == 5

        # Users last month: u5 = 1
        assert data["users_last_month"] == 1

        # Total firm admins: u1, u2 = 2
        assert data["total_firm_admins"] == 2

        # Total lawyers: u3, u4 = 2
        assert data["total_lawyers"] == 2

    def test_firm_admin_can_access_stats(self, api_client, firm_admin):
        client = get_auth_client(api_client, firm_admin)
        response = client.get(STATS_URL)
        assert response.status_code == status.HTTP_200_OK
        assert "total_users" in response.data
        assert "total_active_users" in response.data

    def test_lawyer_cannot_access_stats(self, api_client, lawyer):
        client = get_auth_client(api_client, lawyer)
        response = client.get(STATS_URL)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_cannot_access_stats(self, api_client):
        response = api_client.get(STATS_URL)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
