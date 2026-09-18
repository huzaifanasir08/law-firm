from django.db import models
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
