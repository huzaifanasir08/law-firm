import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class MatterStatus(models.TextChoices):
    """Statuses for a legal matter."""

    OPEN = "OPEN", _("Open")
    IN_PROGRESS = "IN_PROGRESS", _("In Progress")
    PENDING = "PENDING", _("Pending")
    CLOSED = "CLOSED", _("Closed")


class MatterPriority(models.TextChoices):
    """Priority levels for a legal matter."""

    LOW = "LOW", _("Low")
    MEDIUM = "MEDIUM", _("Medium")
    HIGH = "HIGH", _("High")
    URGENT = "URGENT", _("Urgent")


def generate_case_number() -> str:
    """Generate a unique human-friendly case reference number."""
    now_str = timezone.now().strftime("%Y%m")
    unique_suffix = uuid.uuid4().hex[:6].upper()
    return f"MAT-{now_str}-{unique_suffix}"


class Matter(models.Model):
    """
    Represents a legal matter or case.
    Scoped to a lawyer, assigned to a client, and affiliated with a firm.
    """

    title = models.CharField(_("matter title"), max_length=255, db_index=True)
    case_number = models.CharField(
        _("case number"),
        max_length=100,
        unique=True,
        db_index=True,
        default=generate_case_number,
    )
    description = models.TextField(_("description"), blank=True, default="")
    lawyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="matters",
        verbose_name=_("assigned lawyer"),
        db_index=True,
    )
    client = models.ForeignKey(
        "lawyer.Client",
        on_delete=models.CASCADE,
        related_name="matters",
        verbose_name=_("client"),
        db_index=True,
    )
    firm = models.ForeignKey(
        "firm.Firm",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="matters",
        verbose_name=_("firm"),
        db_index=True,
    )
    status = models.CharField(
        _("status"),
        max_length=30,
        choices=MatterStatus.choices,
        default=MatterStatus.OPEN,
        db_index=True,
    )
    priority = models.CharField(
        _("priority"),
        max_length=20,
        choices=MatterPriority.choices,
        default=MatterPriority.MEDIUM,
    )
    due_date = models.DateField(_("due date"), null=True, blank=True, db_index=True)
    closed_at = models.DateTimeField(_("closed at"), null=True, blank=True)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("matter")
        verbose_name_plural = _("matters")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.case_number} - {self.title}"

    @property
    def is_open(self) -> bool:
        return self.status in [MatterStatus.OPEN, MatterStatus.IN_PROGRESS, MatterStatus.PENDING]

    @property
    def is_closed(self) -> bool:
        return self.status == MatterStatus.CLOSED

    @property
    def is_due(self) -> bool:
        if not self.due_date or self.is_closed:
            return False
        return self.due_date <= timezone.now().date()
