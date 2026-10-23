"""
Tests for GET /api/subscription/me/
"""

from datetime import timedelta
from decimal import Decimal
import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import UserRole
from apps.firm.models import Firm, FirmType
from apps.subscription.models import PaymentMethod, Plan, PlanCycle, Subscription, SubscriptionStatus, SubscriptionType, Transaction, TransactionStatus

SUBSCRIPTION_ME_URL = "/api/subscription/me/"


@pytest.fixture
def plan(db):
    return Plan.objects.create(
        name="Enterprise Tier",
        price=Decimal("199.99"),
        cycle=PlanCycle.MONTHLY,
        is_active=True,
    )


@pytest.fixture
def firm(db):
    return Firm.objects.create(
        name="Apex Legal Advocates",
        type=FirmType.MULTI,
        is_active=True,
    )


@pytest.mark.django_db
class TestSelfSubscriptionView:
    """Test suite for retrieving the current user's firm subscription details."""

    def test_get_self_subscription_authenticated_returns_200(self, api_client, make_user, firm, plan):
        """Authenticated user whose firm has an active subscription receives full details."""
        user = make_user(
            email="lawyer@apex.com",
            role=UserRole.LAWYER,
            firm=firm,
        )
        txn = Transaction.objects.create(
            amount=plan.price,
            status=TransactionStatus.COMPLETED,
            payment_method=PaymentMethod.ONLINE,
            transaction_id="TXN-APEX-001",
            firm=firm,
            firm_admin=user,
        )
        sub = Subscription.objects.create(
            plan=plan,
            transaction=txn,
            firm=firm,
            firm_admin=user,
            status=SubscriptionStatus.ACTIVE,
            started_at=timezone.now() - timedelta(days=5),
            ends_at=timezone.now() + timedelta(days=25),
            subscription_type=SubscriptionType.MONTHLY,
        )

        refresh = RefreshToken.for_user(user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

        response = api_client.get(SUBSCRIPTION_ME_URL)
        assert response.status_code == status.HTTP_200_OK

        data = response.data
        assert data["id"] == sub.id
        assert data["plan"] == plan.id
        assert data["plan_details"]["name"] == "Enterprise Tier"
        assert Decimal(data["plan_details"]["price"]) == plan.price
        assert data["status"] == SubscriptionStatus.ACTIVE
        assert data["is_valid"] is True
        assert data["is_trial"] is False
        assert data["firm"] == firm.id
        assert data["firm_name"] == firm.name
        assert data["firm_admin"] == user.id
        assert data["transaction_details"]["transaction_id"] == "TXN-APEX-001"

    def test_get_self_subscription_for_clerk_role(self, api_client, make_user, firm, plan):
        """Any authenticated firm member (e.g., Clerk) can retrieve the firm subscription details."""
        user = make_user(
            email="clerk@apex.com",
            role=UserRole.CLERK,
            firm=firm,
        )
        Subscription.objects.create(
            plan=plan,
            firm=firm,
            firm_admin=user,
            status=SubscriptionStatus.ACTIVE,
            started_at=timezone.now() - timedelta(days=1),
            ends_at=timezone.now() + timedelta(days=29),
        )

        refresh = RefreshToken.for_user(user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

        response = api_client.get(SUBSCRIPTION_ME_URL)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["firm_name"] == firm.name
        assert response.data["is_valid"] is True

    def test_get_self_subscription_returns_trial_details(self, api_client, make_user, firm, plan):
        """Firm with an active trial returns trial-specific dates and flags."""
        user = make_user(
            email="trialuser@apex.com",
            role=UserRole.FIRM_ADMIN,
            firm=firm,
        )
        start_time = timezone.now() - timedelta(days=3)
        end_time = timezone.now() + timedelta(days=11)
        Subscription.objects.create(
            plan=plan,
            firm=firm,
            firm_admin=user,
            status=SubscriptionStatus.TRIAL,
            is_trial=True,
            trial_duration_days=14,
            started_at=start_time,
            trial_ends_at=end_time,
            ends_at=end_time,
        )

        refresh = RefreshToken.for_user(user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

        response = api_client.get(SUBSCRIPTION_ME_URL)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == SubscriptionStatus.TRIAL
        assert response.data["is_trial"] is True
        assert response.data["trial_duration_days"] == 14
        assert response.data["trial_ends_at"] is not None
        assert response.data["is_valid"] is True

    def test_get_self_subscription_picks_active_over_expired(self, api_client, make_user, firm, plan):
        """When multiple subscriptions exist, the currently valid active one is selected."""
        user = make_user(
            email="lawyer2@apex.com",
            role=UserRole.LAWYER,
            firm=firm,
        )
        # Older expired subscription
        Subscription.objects.create(
            plan=plan,
            firm=firm,
            firm_admin=user,
            status=SubscriptionStatus.EXPIRED,
            started_at=timezone.now() - timedelta(days=40),
            ends_at=timezone.now() - timedelta(days=10),
        )
        # Newer active subscription
        active_sub = Subscription.objects.create(
            plan=plan,
            firm=firm,
            firm_admin=user,
            status=SubscriptionStatus.ACTIVE,
            started_at=timezone.now() - timedelta(days=2),
            ends_at=timezone.now() + timedelta(days=28),
        )

        refresh = RefreshToken.for_user(user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

        response = api_client.get(SUBSCRIPTION_ME_URL)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == active_sub.id
        assert response.data["status"] == SubscriptionStatus.ACTIVE
        assert response.data["is_valid"] is True

    def test_get_self_subscription_returns_latest_when_expired(self, api_client, make_user, firm, plan):
        """If the subscription has expired, it returns the latest subscription with is_valid=False."""
        user = make_user(
            email="expireduser@apex.com",
            role=UserRole.LAWYER,
            firm=firm,
        )
        expired_sub = Subscription.objects.create(
            plan=plan,
            firm=firm,
            firm_admin=user,
            status=SubscriptionStatus.EXPIRED,
            started_at=timezone.now() - timedelta(days=35),
            ends_at=timezone.now() - timedelta(days=5),
        )

        refresh = RefreshToken.for_user(user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

        response = api_client.get(SUBSCRIPTION_ME_URL)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == expired_sub.id
        assert response.data["is_valid"] is False

    def test_get_self_subscription_user_without_firm_returns_404(self, api_client, make_user):
        """User without any firm receives a 404 with a helpful message."""
        user = make_user(
            email="nofirm@example.com",
            role=UserRole.SUPER_ADMIN,
            is_staff=True,
            is_superuser=True,
            firm=None,
        )
        refresh = RefreshToken.for_user(user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

        response = api_client.get(SUBSCRIPTION_ME_URL)
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not associated with any firm" in response.data["error"]

    def test_get_self_subscription_firm_without_subscription_returns_404(self, api_client, make_user, firm):
        """User whose firm has 0 subscriptions receives a 404 with a helpful message."""
        user = make_user(
            email="emptyfirm@apex.com",
            role=UserRole.LAWYER,
            firm=firm,
        )
        refresh = RefreshToken.for_user(user)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

        response = api_client.get(SUBSCRIPTION_ME_URL)
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "No subscription found" in response.data["error"]

    def test_get_self_subscription_unauthenticated_returns_401(self, api_client):
        """Unauthenticated requests are denied with 401."""
        response = api_client.get(SUBSCRIPTION_ME_URL)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
