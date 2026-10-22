"""
Tests for subscription and trial validation during authentication (POST /api/accounts/login/ and OTP).
"""

from datetime import timedelta
import pytest
from django.core import mail
from django.utils import timezone
from rest_framework import status

from apps.accounts.models import OTPPurpose, UserRole
from apps.accounts.tokens import generate_otp
from apps.firm.models import Firm, FirmType
from apps.subscription.models import Plan, PlanCycle, Subscription, SubscriptionStatus

LOGIN_URL = "/api/accounts/login/"
OTP_SEND_URL = "/api/accounts/otp/send/"
OTP_VERIFY_URL = "/api/accounts/otp/verify/"


@pytest.fixture
def plan(db):
    return Plan.objects.create(
        name="Pro Legal Tier",
        price=99.00,
        cycle=PlanCycle.MONTHLY,
        is_active=True,
    )


@pytest.fixture
def active_firm(db):
    return Firm.objects.create(
        name="Justice Law Firm",
        type=FirmType.MULTI,
        is_active=True,
    )


@pytest.mark.django_db
class TestSubscriptionLoginValidation:
    """Test suite ensuring users cannot log in without a valid firm subscription or trial."""

    # ── Missing firm ──────────────────────────────────────────────────────────

    def test_login_blocked_if_non_superadmin_has_no_firm(self, api_client, make_user):
        """A lawyer/clerk/firm_admin with no firm assigned is denied login with 403."""
        make_user(
            email="orphan@example.com",
            password="GoodP@ssword123",
            role=UserRole.LAWYER,
            firm=None,
        )
        response = api_client.post(
            LOGIN_URL,
            {"email": "orphan@example.com", "password": "GoodP@ssword123"},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "not associated with any firm" in response.data["error"]

    # ── Inactive firm ─────────────────────────────────────────────────────────

    def test_login_blocked_if_firm_is_inactive(self, api_client, make_user, plan):
        """A user whose firm is deactivated is denied login with 403."""
        inactive_firm = Firm.objects.create(
            name="Deactivated Firm",
            type=FirmType.MULTI,
            is_active=False,
        )
        user = make_user(
            email="inactivefirm@example.com",
            password="GoodP@ssword123",
            role=UserRole.LAWYER,
            firm=inactive_firm,
        )
        # Even with an active subscription, firm itself is inactive
        Subscription.objects.create(
            plan=plan,
            firm=inactive_firm,
            firm_admin=user,
            status=SubscriptionStatus.ACTIVE,
            ends_at=timezone.now() + timedelta(days=30),
        )

        response = api_client.post(
            LOGIN_URL,
            {"email": "inactivefirm@example.com", "password": "GoodP@ssword123"},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "inactive" in response.data["error"]

    # ── No subscription on firm ───────────────────────────────────────────────

    def test_login_blocked_if_firm_has_no_subscription(self, api_client, make_user, active_firm):
        """A user whose firm has never subscribed or started a trial is denied login with 403."""
        make_user(
            email="nosub@example.com",
            password="GoodP@ssword123",
            role=UserRole.LAWYER,
            firm=active_firm,
        )
        response = api_client.post(
            LOGIN_URL,
            {"email": "nosub@example.com", "password": "GoodP@ssword123"},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "does not have an active subscription or valid trial" in response.data["error"]

    # ── Expired subscription ──────────────────────────────────────────────────

    def test_login_blocked_if_firm_subscription_expired_by_status(self, api_client, make_user, active_firm, plan):
        """A user whose firm subscription status is EXPIRED is denied login with 403."""
        user = make_user(
            email="expiredstatus@example.com",
            password="GoodP@ssword123",
            role=UserRole.LAWYER,
            firm=active_firm,
        )
        Subscription.objects.create(
            plan=plan,
            firm=active_firm,
            firm_admin=user,
            status=SubscriptionStatus.EXPIRED,
            ends_at=timezone.now() - timedelta(days=1),
        )
        response = api_client.post(
            LOGIN_URL,
            {"email": "expiredstatus@example.com", "password": "GoodP@ssword123"},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "subscription has expired" in response.data["error"]

    def test_login_blocked_if_firm_subscription_expired_by_date(self, api_client, make_user, active_firm, plan):
        """A user whose firm subscription ends_at is in the past is denied login with 403."""
        user = make_user(
            email="expireddate@example.com",
            password="GoodP@ssword123",
            role=UserRole.FIRM_ADMIN,
            firm=active_firm,
        )
        Subscription.objects.create(
            plan=plan,
            firm=active_firm,
            firm_admin=user,
            status=SubscriptionStatus.ACTIVE,
            ends_at=timezone.now() - timedelta(hours=2),
        )
        response = api_client.post(
            LOGIN_URL,
            {"email": "expireddate@example.com", "password": "GoodP@ssword123"},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "subscription has expired" in response.data["error"]

    # ── Expired trial ─────────────────────────────────────────────────────────

    def test_login_blocked_if_firm_trial_expired(self, api_client, make_user, active_firm, plan):
        """A user whose firm trial period has ended is denied login with 403."""
        user = make_user(
            email="expiredtrial@example.com",
            password="GoodP@ssword123",
            role=UserRole.LAWYER,
            firm=active_firm,
        )
        Subscription.objects.create(
            plan=plan,
            firm=active_firm,
            firm_admin=user,
            status=SubscriptionStatus.TRIAL,
            is_trial=True,
            trial_duration_days=14,
            trial_ends_at=timezone.now() - timedelta(days=1),
            ends_at=timezone.now() - timedelta(days=1),
        )
        response = api_client.post(
            LOGIN_URL,
            {"email": "expiredtrial@example.com", "password": "GoodP@ssword123"},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "trial period has expired" in response.data["error"]

    # ── Canceled subscription ─────────────────────────────────────────────────

    def test_login_blocked_if_firm_subscription_canceled(self, api_client, make_user, active_firm, plan):
        """A user whose firm subscription was canceled is denied login with 403."""
        user = make_user(
            email="canceledsub@example.com",
            password="GoodP@ssword123",
            role=UserRole.LAWYER,
            firm=active_firm,
        )
        Subscription.objects.create(
            plan=plan,
            firm=active_firm,
            firm_admin=user,
            status=SubscriptionStatus.CANCELED,
            canceled_at=timezone.now() - timedelta(days=1),
        )
        response = api_client.post(
            LOGIN_URL,
            {"email": "canceledsub@example.com", "password": "GoodP@ssword123"},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "subscription has been canceled" in response.data["error"]

    # ── Valid active subscription ─────────────────────────────────────────────

    def test_login_succeeds_with_valid_paid_subscription(self, api_client, make_user, active_firm, plan):
        """A user whose firm has an active paid subscription logs in successfully (200)."""
        user = make_user(
            email="activepaid@example.com",
            password="GoodP@ssword123",
            role=UserRole.LAWYER,
            firm=active_firm,
        )
        Subscription.objects.create(
            plan=plan,
            firm=active_firm,
            firm_admin=user,
            status=SubscriptionStatus.ACTIVE,
            started_at=timezone.now() - timedelta(days=5),
            ends_at=timezone.now() + timedelta(days=25),
        )
        response = api_client.post(
            LOGIN_URL,
            {"email": "activepaid@example.com", "password": "GoodP@ssword123"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data
        assert "refresh" in response.data
        assert response.data["user"]["email"] == "activepaid@example.com"

    # ── Valid trial subscription ──────────────────────────────────────────────

    def test_login_succeeds_with_valid_trial(self, api_client, make_user, active_firm, plan):
        """A user whose firm has an active trial logs in successfully (200)."""
        user = make_user(
            email="activetrial@example.com",
            password="GoodP@ssword123",
            role=UserRole.CLERK,
            firm=active_firm,
        )
        Subscription.objects.create(
            plan=plan,
            firm=active_firm,
            firm_admin=user,
            status=SubscriptionStatus.TRIAL,
            is_trial=True,
            trial_duration_days=14,
            started_at=timezone.now() - timedelta(days=2),
            trial_ends_at=timezone.now() + timedelta(days=12),
            ends_at=timezone.now() + timedelta(days=12),
        )
        response = api_client.post(
            LOGIN_URL,
            {"email": "activetrial@example.com", "password": "GoodP@ssword123"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data
        assert "refresh" in response.data

    # ── Multiple subscriptions (historical expired + new active) ───────────────

    def test_login_succeeds_when_firm_has_historical_expired_and_current_active(
        self, api_client, make_user, active_firm, plan
    ):
        """Firm had an expired trial in the past, but renewed with an active plan."""
        user = make_user(
            email="renewed@example.com",
            password="GoodP@ssword123",
            role=UserRole.LAWYER,
            firm=active_firm,
        )
        # Old expired trial
        Subscription.objects.create(
            plan=plan,
            firm=active_firm,
            firm_admin=user,
            status=SubscriptionStatus.EXPIRED,
            is_trial=True,
            trial_duration_days=14,
            started_at=timezone.now() - timedelta(days=60),
            trial_ends_at=timezone.now() - timedelta(days=46),
            ends_at=timezone.now() - timedelta(days=46),
        )
        # Current active subscription
        Subscription.objects.create(
            plan=plan,
            firm=active_firm,
            firm_admin=user,
            status=SubscriptionStatus.ACTIVE,
            started_at=timezone.now() - timedelta(days=2),
            ends_at=timezone.now() + timedelta(days=28),
        )
        response = api_client.post(
            LOGIN_URL,
            {"email": "renewed@example.com", "password": "GoodP@ssword123"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data

    # ── Super Admin exemption ─────────────────────────────────────────────────

    def test_super_admin_without_firm_can_login(self, api_client, make_user):
        """Super Admins are platform administrators and are exempt from firm subscription checks."""
        make_user(
            email="platform_admin@example.com",
            password="GoodP@ssword123",
            role=UserRole.SUPER_ADMIN,
            is_staff=True,
            is_superuser=True,
            firm=None,
        )
        response = api_client.post(
            LOGIN_URL,
            {"email": "platform_admin@example.com", "password": "GoodP@ssword123"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data

    def test_super_admin_with_expired_firm_can_login(self, api_client, make_user, active_firm, plan):
        """Super Admins attached to a firm with expired subscription can still log in."""
        user = make_user(
            email="admin_expired_firm@example.com",
            password="GoodP@ssword123",
            role=UserRole.SUPER_ADMIN,
            is_staff=True,
            is_superuser=True,
            firm=active_firm,
        )
        Subscription.objects.create(
            plan=plan,
            firm=active_firm,
            firm_admin=user,
            status=SubscriptionStatus.EXPIRED,
            ends_at=timezone.now() - timedelta(days=1),
        )
        response = api_client.post(
            LOGIN_URL,
            {"email": "admin_expired_firm@example.com", "password": "GoodP@ssword123"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data

    # ── Two-Factor Authentication (2FA) ───────────────────────────────────────

    def test_2fa_login_blocked_and_no_otp_sent_if_firm_subscription_expired(
        self, api_client, make_user, active_firm, plan
    ):
        """If user has 2FA enabled but firm subscription expired, 403 is returned and no OTP is sent."""
        user = make_user(
            email="user2fa_expired@example.com",
            password="GoodP@ssword123",
            role=UserRole.LAWYER,
            firm=active_firm,
            two_factor_enabled=True,
        )
        Subscription.objects.create(
            plan=plan,
            firm=active_firm,
            firm_admin=user,
            status=SubscriptionStatus.EXPIRED,
            ends_at=timezone.now() - timedelta(days=1),
        )
        response = api_client.post(
            LOGIN_URL,
            {"email": "user2fa_expired@example.com", "password": "GoodP@ssword123"},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "subscription has expired" in response.data["error"]
        assert len(mail.outbox) == 0

    def test_otp_send_blocked_if_firm_subscription_expired(
        self, api_client, make_user, active_firm, plan
    ):
        """Direct call to /api/accounts/otp/send/ is rejected with 403 if firm subscription is expired."""
        user = make_user(
            email="user_otp_send@example.com",
            password="GoodP@ssword123",
            role=UserRole.LAWYER,
            firm=active_firm,
            two_factor_enabled=True,
        )
        Subscription.objects.create(
            plan=plan,
            firm=active_firm,
            firm_admin=user,
            status=SubscriptionStatus.EXPIRED,
            ends_at=timezone.now() - timedelta(days=1),
        )
        response = api_client.post(
            OTP_SEND_URL,
            {"email": "user_otp_send@example.com"},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "subscription has expired" in response.data["error"]

    def test_otp_verify_blocked_if_firm_subscription_expired(
        self, api_client, make_user, active_firm, plan
    ):
        """Direct call to /api/accounts/otp/verify/ is rejected with 403 if firm subscription is expired."""
        user = make_user(
            email="user_otp_verify@example.com",
            password="GoodP@ssword123",
            role=UserRole.LAWYER,
            firm=active_firm,
            two_factor_enabled=True,
        )
        raw_code, _ = generate_otp(user, purpose=OTPPurpose.LOGIN)

        # Expired subscription
        Subscription.objects.create(
            plan=plan,
            firm=active_firm,
            firm_admin=user,
            status=SubscriptionStatus.EXPIRED,
            ends_at=timezone.now() - timedelta(days=1),
        )
        response = api_client.post(
            OTP_VERIFY_URL,
            {"email": "user_otp_verify@example.com", "code": raw_code},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "subscription has expired" in response.data["error"]
