from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Client(models.Model):
    """
    Represents a client managed by a lawyer.
    A client is system data with a 'CLIENT' role but without user login credentials.
    """

    lawyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="clients",
        verbose_name=_("assigned lawyer"),
        db_index=True,
    )
    firm = models.ForeignKey(
        "firm.Firm",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="clients",
        verbose_name=_("firm"),
    )
    name = models.CharField(_("client name"), max_length=255, db_index=True)
    email = models.EmailField(_("email address"), blank=True, default="")
    phone = models.CharField(_("phone number"), max_length=30, blank=True, default="")
    address = models.TextField(_("address"), blank=True, default="")
    role = models.CharField(_("role"), max_length=20, default="CLIENT")
    is_active = models.BooleanField(
        _("active status"),
        default=True,
        help_text=_("Designates whether this client is active. Used for soft deletion."),
    )
    notes = models.TextField(_("notes"), blank=True, default="")
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("client")
        verbose_name_plural = _("clients")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} (Client)"
