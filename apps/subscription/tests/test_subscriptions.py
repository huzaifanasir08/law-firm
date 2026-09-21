from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import UserRole
from apps.firm.models import Firm, FirmType
from apps.subscription.models import (
    PaymentMethod,
    Plan,
    PlanCycle,
    Subscription,
    SubscriptionStatus,
    SubscriptionType,
    Transaction,
    TransactionStatus,
)


@pytest.fixture
def superadmin_client(api_client, super_admin):
    refresh = RefreshToken.for_user(super_admin)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    api_client._user = super_admin
    return api_client


@pytest.fixture
def lawyer_client(api_client, lawyer):
    refresh = RefreshToken.for_user(lawyer)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    api_client._user = lawyer
    return api_client


@pytest.fixture
def test_firm(db):
    return Firm.objects.create(
        name="Apex Legal Group",
        type=FirmType.MULTI,
        email="contact@apexlegal.test",
        phone="+123456789",
    )


@pytest.fixture
def firm_admin_user(make_user, test_firm):
    return make_user(
        email="firmadmin_sub@test.com",
        name="Firm Administrator",
        role=UserRole.FIRM_ADMIN,
        firm=test_firm,
    )


@pytest.fixture
def monthly_plan(db):
    return Plan.objects.create(
        name="Starter Monthly",
        description="Standard features for small firms",
        price=Decimal("99.00"),
        cycle=PlanCycle.MONTHLY,
        is_active=True,
        is_public=True,
        is_popular=False,
    )


@pytest.fixture
def yearly_plan(db):
    return Plan.objects.create(
        name="Enterprise Yearly",
        description="Full features for growing firms",
        price=Decimal("999.00"),
        cycle=PlanCycle.YEARLY,
        is_active=True,
        is_public=True,
        is_popular=True,
    )


@pytest.mark.django_db
class TestPlanManagement:
    """Test plan CRUD and single popular plan constraint."""

    list_url = reverse("administration:plan-list-create")

    def test_popular_one_at_a_time_constraint(self, db):
        plan1 = Plan.objects.create(
            name="Plan 1",
            price=Decimal("50.00"),
            cycle=PlanCycle.MONTHLY,
            is_popular=True,
        )
        assert plan1.is_popular is True

        plan2 = Plan.objects.create(
            name="Plan 2",
            price=Decimal("100.00"),
            cycle=PlanCycle.MONTHLY,
            is_popular=True,
        )
        plan1.refresh_from_db()
        assert plan1.is_popular is False
        assert plan2.is_popular is True

        # Updating plan 1 back to popular unsets plan 2
        plan1.is_popular = True
        plan1.save()
        plan2.refresh_from_db()
        assert plan1.is_popular is True
        assert plan2.is_popular is False

    def test_super_admin_create_plan_api(self, superadmin_client):
        data = {
            "name": "Custom Growth Plan",
            "description": "Tailored for expanding firms",
            "price": "149.50",
            "cycle": "monthly",
            "is_active": True,
            "is_public": True,
            "is_popular": True,
        }
        response = superadmin_client.post(self.list_url, data, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "Custom Growth Plan"
        assert Decimal(response.data["price"]) == Decimal("149.50")
        assert response.data["is_popular"] is True

    def test_public_plans_endpoint(self, api_client, monthly_plan, yearly_plan):
        # Create an inactive private plan
        Plan.objects.create(
            name="Archived Plan",
            price=Decimal("10.00"),
            cycle=PlanCycle.MONTHLY,
            is_active=False,
            is_public=False,
        )
        url = reverse("subscription:public-plan-list")
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        # Only active and public plans returned
        names = [p["name"] for p in response.data]
        assert "Starter Monthly" in names
        assert "Enterprise Yearly" in names
        assert "Archived Plan" not in names

    def test_non_superadmin_cannot_create_plan(self, lawyer_client):
        data = {
            "name": "Unauthorized Plan",
            "price": "50.00",
            "cycle": "monthly",
        }
        response = lawyer_client.post(self.list_url, data, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestAdminCompositeSubscriptionCreation:
    """Test composite Super Admin subscription creation with auto-calculated fields."""

    url = reverse("administration:subscription-list-create")

    def test_create_paid_monthly_subscription_auto_calculates_fields(
        self, superadmin_client, firm_admin_user, monthly_plan
    ):
        data = {
            "user": firm_admin_user.id,
            "plan": monthly_plan.id,
            "payment_method": "online",
            "sender_bank_account": "ACC-123456789",
            "receiver_bank_account": "ACC-987654321",
        }
        response = superadmin_client.post(self.url, data, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        res_data = response.data

        # Verify subscription was created and auto-calculated
        assert res_data["status"] == SubscriptionStatus.ACTIVE
        assert res_data["is_trial"] is False
        assert res_data["subscription_type"] == SubscriptionType.MONTHLY
        assert res_data["firm"] == firm_admin_user.firm.id
        assert res_data["firm_name"] == firm_admin_user.firm.name
        assert res_data["firm_admin"] == firm_admin_user.id
        assert res_data["ends_at"] is not None

        # Verify transaction was created and auto-linked
        assert res_data["transaction"] is not None
        txn_data = res_data["transaction_details"]
        assert Decimal(txn_data["amount"]) == monthly_plan.price
        assert txn_data["status"] == TransactionStatus.COMPLETED
        assert txn_data["payment_method"] == PaymentMethod.ONLINE
        assert txn_data["sender_bank_account"] == "ACC-123456789"
        assert txn_data["receiver_bank_account"] == "ACC-987654321"
        assert txn_data["transaction_id"].startswith("TXN-")

        # Check DB records
        sub = Subscription.objects.get(id=res_data["id"])
        assert sub.transaction is not None
        assert sub.transaction.amount == monthly_plan.price

    def test_create_trial_subscription_auto_calculates_trial_dates(
        self, superadmin_client, firm_admin_user, monthly_plan
    ):
        start_time = timezone.now()
        data = {
            "user": firm_admin_user.id,
            "plan": monthly_plan.id,
            "payment_method": "cash",
            "is_trial": True,
            "trial_duration_days": 21,
            "date": start_time.isoformat(),
        }
        response = superadmin_client.post(self.url, data, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        res_data = response.data

        assert res_data["status"] == SubscriptionStatus.TRIAL
        assert res_data["is_trial"] is True
        assert res_data["trial_duration_days"] == 21
        assert res_data["trial_ends_at"] is not None
        assert res_data["ends_at"] == res_data["trial_ends_at"]

        # For trial without amount specified, amount is 0.00
        txn_data = res_data["transaction_details"]
        assert Decimal(txn_data["amount"]) == Decimal("0.00")

    def test_create_subscription_with_explicit_custom_values(
        self, superadmin_client, firm_admin_user, yearly_plan
    ):
        data = {
            "user": firm_admin_user.id,
            "plan": yearly_plan.id,
            "payment_method": "online",
            "amount": "850.00",  # Custom discounted amount
            "transaction_id": "CUSTOM-REF-777",
            "sender_bank_account": "BANK-ALPHA",
            "receiver_bank_account": "BANK-BETA",
            "subscription_type": "yearly",
            "status": "pending",
        }
        response = superadmin_client.post(self.url, data, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        res_data = response.data

        assert res_data["status"] == "pending"
        assert res_data["subscription_type"] == "yearly"
        assert res_data["transaction_details"]["transaction_id"] == "CUSTOM-REF-777"
        assert Decimal(res_data["transaction_details"]["amount"]) == Decimal("850.00")

    def test_create_subscription_user_without_firm_fails(
        self, superadmin_client, make_user, monthly_plan
    ):
        orphan_user = make_user(
            email="orphan@test.com",
            role=UserRole.FIRM_ADMIN,
            firm=None,  # No firm assigned
        )
        data = {
            "user": orphan_user.id,
            "plan": monthly_plan.id,
            "payment_method": "cash",
        }
        response = superadmin_client.post(self.url, data, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        err_msg = response.data.get("error", "") or response.data.get("detail", "")
        assert "firm" in err_msg.lower()

    def test_create_subscription_duplicate_transaction_id_fails(
        self, superadmin_client, firm_admin_user, monthly_plan
    ):
        data1 = {
            "user": firm_admin_user.id,
            "plan": monthly_plan.id,
            "payment_method": "cash",
            "transaction_id": "DUPLICATE-TXN-1",
        }
        res1 = superadmin_client.post(self.url, data1, format="json")
        assert res1.status_code == status.HTTP_201_CREATED

        # Second attempt with same transaction ID
        data2 = {
            "user": firm_admin_user.id,
            "plan": monthly_plan.id,
            "payment_method": "cash",
            "transaction_id": "DUPLICATE-TXN-1",
        }
        res2 = superadmin_client.post(self.url, data2, format="json")
        assert res2.status_code == status.HTTP_400_BAD_REQUEST
        err_msg = res2.data.get("error", "") or res2.data.get("detail", "")
        assert "transaction_id" in err_msg or "already exists" in err_msg


@pytest.mark.django_db
class TestAdminTransactionAndSubscriptionManagement:
    """Test listing, filtering, search, and update for transactions & subscriptions."""

    def test_list_transactions_with_pagination_and_filters(
        self, superadmin_client, firm_admin_user, test_firm
    ):
        Transaction.objects.create(
            amount=Decimal("150.00"),
            status=TransactionStatus.COMPLETED,
            payment_method=PaymentMethod.ONLINE,
            transaction_id="TXN-FILTER-1",
            sender_bank_account="SENDER-1",
            receiver_bank_account="RECV-1",
            firm=test_firm,
            firm_admin=firm_admin_user,
        )
        Transaction.objects.create(
            amount=Decimal("200.00"),
            status=TransactionStatus.PENDING,
            payment_method=PaymentMethod.CASH,
            transaction_id="TXN-FILTER-2",
            firm=test_firm,
            firm_admin=firm_admin_user,
        )

        url = reverse("administration:transaction-list")
        res = superadmin_client.get(url)
        assert res.status_code == status.HTTP_200_OK
        assert res.data["count"] >= 2
        assert "results" in res.data

        # Filter by payment_method=cash
        res_filtered = superadmin_client.get(f"{url}?payment_method=cash")
        assert res_filtered.status_code == status.HTTP_200_OK
        assert res_filtered.data["count"] == 1
        assert res_filtered.data["results"][0]["transaction_id"] == "TXN-FILTER-2"

        # Search by transaction_id
        res_search = superadmin_client.get(f"{url}?search=FILTER-1")
        assert res_search.status_code == status.HTTP_200_OK
        assert res_search.data["count"] == 1
        assert res_search.data["results"][0]["transaction_id"] == "TXN-FILTER-1"

    def test_super_admin_update_subscription_and_cancel(
        self, superadmin_client, firm_admin_user, test_firm, monthly_plan
    ):
        sub = Subscription.objects.create(
            plan=monthly_plan,
            status=SubscriptionStatus.ACTIVE,
            firm=test_firm,
            firm_admin=firm_admin_user,
            subscription_type=SubscriptionType.MONTHLY,
            started_at=timezone.now(),
            ends_at=timezone.now() + timedelta(days=30),
        )

        detail_url = reverse("administration:subscription-detail", kwargs={"pk": sub.pk})
        patch_data = {
            "status": "canceled",
        }
        res = superadmin_client.patch(detail_url, patch_data, format="json")
        assert res.status_code == status.HTTP_200_OK
        sub.refresh_from_db()
        assert sub.status == SubscriptionStatus.CANCELED
        assert sub.canceled_at is not None

    def test_non_superadmin_cannot_access_transactions_or_subscriptions(
        self, lawyer_client
    ):
        txn_url = reverse("administration:transaction-list")
        sub_url = reverse("administration:subscription-list-create")
        assert lawyer_client.get(txn_url).status_code == status.HTTP_403_FORBIDDEN
        assert lawyer_client.get(sub_url).status_code == status.HTTP_403_FORBIDDEN
