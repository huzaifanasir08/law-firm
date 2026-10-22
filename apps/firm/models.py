from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class FirmType(models.TextChoices):
    """Types of legal firms supported by the platform."""

    INDIVIDUAL = "INDIVIDUAL", _("Individual")
    MULTI = "MULTI", _("Multi")


class Firm(models.Model):
    """
    Represents a Law Firm entity in the platform.
    Lawyers, clerks, and matters are associated with a firm.
    """

    name = models.CharField(_("firm name"), max_length=255, db_index=True)
    type = models.CharField(
        _("firm type"),
        max_length=20,
        choices=FirmType.choices,
        default=FirmType.MULTI,
        db_index=True,
        help_text=_("Designates whether this firm is individual (solo practitioner) or multi-lawyer."),
    )
    registration_number = models.CharField(
        _("registration/license number"),
        max_length=100,
        blank=True,
        default="",
    )
    email = models.EmailField(_("firm email"), blank=True, default="")
    phone = models.CharField(_("phone number"), max_length=30, blank=True, default="")
    address = models.TextField(_("address"), blank=True, default="")
    is_active = models.BooleanField(
        _("active status"),
        default=True,
        help_text=_("Designates whether this firm is active."),
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("firm")
        verbose_name_plural = _("firms")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.name

    @property
    def is_individual(self) -> bool:
        return self.type == FirmType.INDIVIDUAL

    @property
    def is_multi(self) -> bool:
        return self.type == FirmType.MULTI

    def has_valid_subscription(self) -> bool:
        """Returns True if the firm is active and has an active subscription or valid trial."""
        is_valid, _ = self.get_subscription_status()
        return is_valid

    def get_subscription_status(self) -> tuple[bool, str]:
        """
        Evaluates the firm's subscription and trial status.
        Returns a tuple of (is_valid: bool, reason_message: str).
        """
        if not self.is_active:
            return False, str(_("Your firm account is inactive. Please contact support."))

        from apps.subscription.models import SubscriptionStatus

        now = timezone.now()
        subscriptions = self.subscriptions.all().order_by("-created_at")

        if not subscriptions.exists():
            return False, str(_("Your firm does not have an active subscription or valid trial. Please subscribe to continue."))

        # Check if there is any currently valid subscription
        for sub in subscriptions:
            if sub.is_valid:
                return True, "Valid subscription"

        # None are currently valid; identify specific helpful reason from the most recent one
        latest = subscriptions.first()

        if latest.status == SubscriptionStatus.CANCELED or (latest.canceled_at and latest.canceled_at <= now):
            return False, str(_("Your firm's subscription has been canceled. Please renew your subscription to continue."))

        if (latest.is_trial or latest.status == SubscriptionStatus.TRIAL) and (
            (latest.trial_ends_at and latest.trial_ends_at <= now)
            or (latest.ends_at and latest.ends_at <= now)
            or latest.status == SubscriptionStatus.EXPIRED
        ):
            return False, str(_("Your firm's trial period has expired. Please subscribe to a plan to continue."))

        if (latest.ends_at and latest.ends_at <= now) or latest.status == SubscriptionStatus.EXPIRED:
            return False, str(_("Your firm's subscription has expired. Please renew your subscription to continue."))

        return False, str(_("Your firm does not have a valid subscription or active trial. Please subscribe or renew to continue."))
