import uuid
from django.conf import settings
from django.db import models, transaction as db_transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class PlanCycle(models.TextChoices):
    MONTHLY = "monthly", _("Monthly")
    YEARLY = "yearly", _("Yearly")


class PaymentMethod(models.TextChoices):
    CASH = "cash", _("Cash")
    ONLINE = "online", _("Online")


class TransactionStatus(models.TextChoices):
    PENDING = "pending", _("Pending")
    COMPLETED = "completed", _("Completed")
    FAILED = "failed", _("Failed")
    REFUNDED = "refunded", _("Refunded")


class SubscriptionStatus(models.TextChoices):
    ACTIVE = "active", _("Active")
    TRIAL = "trial", _("Trial")
    EXPIRED = "expired", _("Expired")
    CANCELED = "canceled", _("Canceled")
    PENDING = "pending", _("Pending")


class SubscriptionType(models.TextChoices):
    MONTHLY = "monthly", _("Monthly")
    YEARLY = "yearly", _("Yearly")


def generate_transaction_id() -> str:
    """Generate a unique human-readable transaction identifier."""
    now_str = timezone.now().strftime("%Y%m%d")
    unique_suffix = uuid.uuid4().hex[:8].upper()
    return f"TXN-{now_str}-{unique_suffix}"


class Plan(models.Model):
    """
    Subscription tier offered to law firms.
    """

    name = models.CharField(_("plan name"), max_length=255, db_index=True)
    description = models.TextField(_("description"), blank=True, default="")
    price = models.DecimalField(_("price"), max_digits=10, decimal_places=2)
    cycle = models.CharField(
        _("billing cycle"),
        max_length=20,
        choices=PlanCycle.choices,
        default=PlanCycle.MONTHLY,
    )
    is_active = models.BooleanField(
        _("active status"),
        default=True,
        help_text=_("Whether this plan is active and available for new subscriptions."),
    )
    is_public = models.BooleanField(
        _("public visibility"),
        default=True,
        help_text=_("Whether this plan is publicly visible to prospective customers."),
    )
    is_popular = models.BooleanField(
        _("popular badge"),
        default=False,
        help_text=_("Designates whether this plan is highlighted as popular (one at a time)."),
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("plan")
        verbose_name_plural = _("plans")
        ordering = ["price", "name"]

    def __str__(self) -> str:
        return f"{self.name} (${self.price}/{self.cycle})"

    def save(self, *args, **kwargs):
        with db_transaction.atomic():
            if self.is_popular:
                # Ensure only one plan is popular at a time
                Plan.objects.filter(is_popular=True).exclude(pk=self.pk).update(is_popular=False)
            super().save(*args, **kwargs)


class Transaction(models.Model):
    """
    Financial payment transaction for a firm's subscription.
    """

    amount = models.DecimalField(_("amount"), max_digits=12, decimal_places=2)
    status = models.CharField(
        _("transaction status"),
        max_length=20,
        choices=TransactionStatus.choices,
        default=TransactionStatus.COMPLETED,
        db_index=True,
    )
    date = models.DateTimeField(_("transaction date"), default=timezone.now)
    payment_method = models.CharField(
        _("payment method"),
        max_length=20,
        choices=PaymentMethod.choices,
        default=PaymentMethod.ONLINE,
    )
    transaction_id = models.CharField(
        _("transaction ID"),
        max_length=100,
        unique=True,
        db_index=True,
        default=generate_transaction_id,
    )
    sender_bank_account = models.CharField(
        _("sender bank account"),
        max_length=100,
        blank=True,
        default="",
    )
    receiver_bank_account = models.CharField(
        _("receiver bank account"),
        max_length=100,
        blank=True,
        default="",
    )
    firm = models.ForeignKey(
        "firm.Firm",
        on_delete=models.CASCADE,
        related_name="transactions",
        verbose_name=_("firm"),
    )
    firm_admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="transactions",
        verbose_name=_("firm admin"),
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("transaction")
        verbose_name_plural = _("transactions")
        ordering = ["-date"]

    def __str__(self) -> str:
        return f"Txn #{self.transaction_id} - ${self.amount} ({self.status})"


class Subscription(models.Model):
    """
    Active or historical firm subscription membership.
    """

    plan = models.ForeignKey(
        Plan,
        on_delete=models.PROTECT,
        related_name="subscriptions",
        verbose_name=_("plan"),
    )
    transaction = models.ForeignKey(
        Transaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subscriptions",
        verbose_name=_("payment transaction"),
    )
    status = models.CharField(
        _("subscription status"),
        max_length=20,
        choices=SubscriptionStatus.choices,
        default=SubscriptionStatus.ACTIVE,
        db_index=True,
    )
    is_trial = models.BooleanField(_("is trial"), default=False)
    trial_duration_days = models.PositiveIntegerField(
        _("trial duration in days"),
        default=0,
    )
    trial_ends_at = models.DateTimeField(_("trial ends at"), null=True, blank=True)
    started_at = models.DateTimeField(_("started at"), default=timezone.now)
    ends_at = models.DateTimeField(_("ends at"), null=True, blank=True)
    firm = models.ForeignKey(
        "firm.Firm",
        on_delete=models.CASCADE,
        related_name="subscriptions",
        verbose_name=_("firm"),
    )
    firm_admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subscriptions",
        verbose_name=_("firm admin"),
    )
    subscription_type = models.CharField(
        _("subscription type"),
        max_length=20,
        choices=SubscriptionType.choices,
        default=SubscriptionType.MONTHLY,
    )
    canceled_at = models.DateTimeField(_("canceled at"), null=True, blank=True)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("subscription")
        verbose_name_plural = _("subscriptions")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.firm.name} - {self.plan.name} ({self.status})"
