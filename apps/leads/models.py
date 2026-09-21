from django.db import models
from django.utils.translation import gettext_lazy as _


class LeadInterest(models.TextChoices):
    """Area of interest for a prospective lead."""

    REGISTER = "register", _("Register")
    INQUIRY = "inquiry", _("Inquiry")
    OTHER = "other", _("Other")


class LeadInterestedFirm(models.TextChoices):
    """Type of firm the lead is interested in."""

    INDIVIDUAL = "individual", _("Individual")
    MULTI = "multi", _("Multi")


class LeadStatus(models.TextChoices):
    """Workflow status of the lead."""

    PENDING = "pending", _("Pending")
    CONTACTED = "contacted", _("Contacted")
    MEETING_SCHEDULED = "meeting_scheduled", _("Meeting Scheduled")
    CONFIRMED = "confirmed", _("Confirmed")


class LeadPreferredTime(models.TextChoices):
    """Preferred time window for contact."""

    TIME_8_10 = "8-10", _("8-10")
    TIME_10_12 = "10-12", _("10-12")
    TIME_12_02 = "12-02", _("12-02")
    TIME_02_04 = "02-04", _("02-04")
    TIME_04_06 = "04-06", _("04-06")
    TIME_06_08 = "06-08", _("06-08")
    TIME_08_10 = "08-10", _("08-10")


class LeadContactWay(models.TextChoices):
    """Preferred communication channel for contact."""

    PHONE_CALL = "phone_call", _("Phone Call")
    WHATSAPP = "whatsapp", _("WhatsApp")


class Lead(models.Model):
    """
    Prospective client inquiry or registration request.
    """

    name = models.CharField(_("full name"), max_length=255, db_index=True)
    email = models.EmailField(
        _("email address"),
        unique=True,
        db_index=True,
        error_messages={
            "unique": _("A lead with this email address already exists."),
        },
    )
    phone = models.CharField(_("phone number"), max_length=30)
    address = models.TextField(_("address"), blank=True, default="")
    interest = models.CharField(
        _("interest"),
        max_length=30,
        choices=LeadInterest.choices,
        db_index=True,
    )
    interested_firm = models.CharField(
        _("interested firm type"),
        max_length=30,
        choices=LeadInterestedFirm.choices,
        db_index=True,
    )
    status = models.CharField(
        _("lead status"),
        max_length=30,
        choices=LeadStatus.choices,
        default=LeadStatus.PENDING,
        db_index=True,
    )
    preferred_time = models.CharField(
        _("preferred time for contact"),
        max_length=30,
        choices=LeadPreferredTime.choices,
    )
    preferred_contact_way = models.CharField(
        _("preferred contact way"),
        max_length=30,
        choices=LeadContactWay.choices,
    )
    notes = models.TextField(
        _("admin internal notes"),
        blank=True,
        default="",
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("lead")
        verbose_name_plural = _("leads")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} <{self.email}> ({self.status})"
