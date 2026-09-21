from datetime import timedelta
from decimal import Decimal

from django.db import transaction as db_transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.accounts.models import User
from apps.firm.models import Firm
from .models import (
    PaymentMethod,
    Plan,
    PlanCycle,
    Subscription,
    SubscriptionStatus,
    SubscriptionType,
    Transaction,
    TransactionStatus,
    generate_transaction_id,
)


class PlanSerializer(serializers.ModelSerializer):
    """Serializer for managing subscription plans."""

    class Meta:
        model = Plan
        fields = [
            "id",
            "name",
            "description",
            "price",
            "cycle",
            "is_active",
            "is_public",
            "is_popular",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class TransactionSerializer(serializers.ModelSerializer):
    """Serializer for financial transactions."""

    firm_name = serializers.CharField(source="firm.name", read_only=True)
    firm_admin_name = serializers.CharField(source="firm_admin.name", read_only=True)
    firm_admin_email = serializers.CharField(source="firm_admin.email", read_only=True)

    class Meta:
        model = Transaction
        fields = [
            "id",
            "amount",
            "status",
            "date",
            "payment_method",
            "transaction_id",
            "sender_bank_account",
            "receiver_bank_account",
            "firm",
            "firm_name",
            "firm_admin",
            "firm_admin_name",
            "firm_admin_email",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class SubscriptionSerializer(serializers.ModelSerializer):
    """Serializer for detailed subscription records."""

    plan_details = PlanSerializer(source="plan", read_only=True)
    transaction_details = TransactionSerializer(source="transaction", read_only=True)
    firm_name = serializers.CharField(source="firm.name", read_only=True)
    firm_admin_name = serializers.CharField(source="firm_admin.name", read_only=True)
    firm_admin_email = serializers.CharField(source="firm_admin.email", read_only=True)

    class Meta:
        model = Subscription
        fields = [
            "id",
            "plan",
            "plan_details",
            "transaction",
            "transaction_details",
            "status",
            "is_trial",
            "trial_duration_days",
            "trial_ends_at",
            "started_at",
            "ends_at",
            "firm",
            "firm_name",
            "firm_admin",
            "firm_admin_name",
            "firm_admin_email",
            "subscription_type",
            "canceled_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class SubscriptionUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating existing subscription details."""

    class Meta:
        model = Subscription
        fields = [
            "plan",
            "status",
            "is_trial",
            "trial_duration_days",
            "trial_ends_at",
            "ends_at",
            "subscription_type",
            "canceled_at",
        ]
        extra_kwargs = {
            "plan": {"required": False},
            "status": {"required": False},
            "is_trial": {"required": False},
            "trial_duration_days": {"required": False},
            "trial_ends_at": {"required": False},
            "ends_at": {"required": False},
            "subscription_type": {"required": False},
            "canceled_at": {"required": False},
        }

    def update(self, instance: Subscription, validated_data: dict) -> Subscription:
        new_status = validated_data.get("status", instance.status)
        if new_status == SubscriptionStatus.CANCELED and not instance.canceled_at:
            validated_data.setdefault("canceled_at", timezone.now())
        return super().update(instance, validated_data)


class AdminCreateSubscriptionSerializer(serializers.Serializer):
    """
    Composite serializer for Super Admins to create both a Transaction and a Subscription
    for a firm admin user in a single form submission, auto-calculating dates, durations,
    pricing, and transaction IDs.
    """

    user = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        help_text=_("Firm Admin user account for this subscription"),
    )
    plan = serializers.PrimaryKeyRelatedField(
        queryset=Plan.objects.all(),
        help_text=_("Plan tier to subscribe to"),
    )
    firm = serializers.PrimaryKeyRelatedField(
        queryset=Firm.objects.all(),
        required=False,
        allow_null=True,
        help_text=_("Firm entity. Auto-resolved from user.firm if omitted."),
    )
    payment_method = serializers.ChoiceField(
        choices=PaymentMethod.choices,
        default=PaymentMethod.ONLINE,
        help_text=_("Payment channel: cash or online"),
    )
    date = serializers.DateTimeField(
        required=False,
        default=timezone.now,
        help_text=_("Date of payment / subscription start. Defaults to now."),
    )
    amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        allow_null=True,
        help_text=_("Transaction amount. Defaults to plan price (or $0.00 for trial)."),
    )
    transaction_id = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        default="",
        help_text=_("Bank or receipt reference ID. Auto-generated if omitted."),
    )
    sender_bank_account = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        default="",
    )
    receiver_bank_account = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        default="",
    )
    transaction_status = serializers.ChoiceField(
        choices=TransactionStatus.choices,
        required=False,
        default=TransactionStatus.COMPLETED,
    )
    status = serializers.ChoiceField(
        choices=SubscriptionStatus.choices,
        required=False,
        allow_null=True,
        help_text=_("Subscription status. Defaults to 'trial' if is_trial else 'active'."),
    )
    is_trial = serializers.BooleanField(
        required=False,
        default=False,
        help_text=_("Whether this is a trial subscription."),
    )
    trial_duration_days = serializers.IntegerField(
        required=False,
        default=0,
        min_value=0,
        help_text=_("Duration of trial in days (defaults to 14 if trial is true)."),
    )
    subscription_type = serializers.ChoiceField(
        choices=SubscriptionType.choices,
        required=False,
        allow_null=True,
        help_text=_("Billing cycle. Defaults to plan cycle (monthly/yearly)."),
    )

    def validate(self, attrs: dict) -> dict:
        user = attrs["user"]
        firm = attrs.get("firm") or user.firm
        if not firm:
            raise serializers.ValidationError(
                {"user": _("The selected user is not associated with any firm. Please assign a firm to the user or provide a firm.")}
            )
        attrs["firm"] = firm

        txn_id = attrs.get("transaction_id", "").strip()
        if txn_id and Transaction.objects.filter(transaction_id=txn_id).exists():
            raise serializers.ValidationError(
                {"transaction_id": _("A transaction with this transaction ID already exists.")}
            )

        return attrs

    def create(self, validated_data: dict) -> Subscription:
        user = validated_data["user"]
        plan = validated_data["plan"]
        firm = validated_data["firm"]
        is_trial = validated_data.get("is_trial", False)
        trial_duration = validated_data.get("trial_duration_days", 0)

        # 1. Resolve subscription type (monthly / yearly)
        subscription_type = validated_data.get("subscription_type")
        if not subscription_type:
            subscription_type = (
                SubscriptionType.MONTHLY
                if plan.cycle == PlanCycle.MONTHLY
                else SubscriptionType.YEARLY
            )

        # 2. Resolve start date
        started_at = validated_data.get("date") or timezone.now()

        # 3. Auto-calculate trial dates & subscription status
        if is_trial:
            if trial_duration <= 0:
                trial_duration = 14  # Default 14-day trial
            trial_ends_at = started_at + timedelta(days=trial_duration)
            ends_at = trial_ends_at
            sub_status = validated_data.get("status") or SubscriptionStatus.TRIAL
        else:
            trial_duration = 0
            trial_ends_at = None
            if subscription_type == SubscriptionType.MONTHLY:
                ends_at = started_at + timedelta(days=30)
            else:
                ends_at = started_at + timedelta(days=365)
            sub_status = validated_data.get("status") or SubscriptionStatus.ACTIVE

        # 4. Resolve payment amount
        amount = validated_data.get("amount")
        if amount is None:
            amount = Decimal("0.00") if is_trial else plan.price

        # 5. Resolve transaction ID
        txn_id = validated_data.get("transaction_id", "").strip()
        if not txn_id:
            txn_id = generate_transaction_id()

        # 6. Execute atomic creation of Transaction and Subscription
        with db_transaction.atomic():
            transaction = Transaction.objects.create(
                amount=amount,
                status=validated_data.get("transaction_status", TransactionStatus.COMPLETED),
                date=started_at,
                payment_method=validated_data.get("payment_method", PaymentMethod.ONLINE),
                transaction_id=txn_id,
                sender_bank_account=validated_data.get("sender_bank_account", ""),
                receiver_bank_account=validated_data.get("receiver_bank_account", ""),
                firm=firm,
                firm_admin=user,
            )

            subscription = Subscription.objects.create(
                plan=plan,
                transaction=transaction,
                status=sub_status,
                is_trial=is_trial,
                trial_duration_days=trial_duration,
                trial_ends_at=trial_ends_at,
                started_at=started_at,
                ends_at=ends_at,
                firm=firm,
                firm_admin=user,
                subscription_type=subscription_type,
            )

        return subscription
