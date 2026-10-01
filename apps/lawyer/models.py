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


class TaskStatus(models.TextChoices):
    """Statuses for lawyer and clerk tasks."""

    PENDING = "PENDING", _("Pending")
    ASSIGNED = "ASSIGNED", _("Assigned")
    STARTED = "STARTED", _("Started")
    COMPLETED = "COMPLETED", _("Completed")
    CANCELED = "CANCELED", _("Canceled")


class Task(models.Model):
    """
    Represents a task created by a lawyer and assigned to a clerk.
    Tracks lifecycle timestamps (assigned, started, completed, canceled).
    """

    name = models.CharField(_("task name"), max_length=255, db_index=True)
    desc = models.TextField(_("description"), blank=True, default="")
    lawyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="lawyer_tasks",
        verbose_name=_("assigned lawyer"),
        db_index=True,
    )
    clerk = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="clerk_tasks",
        verbose_name=_("assigned clerk"),
        db_index=True,
    )
    firm = models.ForeignKey(
        "firm.Firm",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tasks",
        verbose_name=_("firm"),
        db_index=True,
    )
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=TaskStatus.choices,
        default=TaskStatus.PENDING,
        db_index=True,
    )
    assigned_at = models.DateTimeField(_("assigned at"), null=True, blank=True)
    started_at = models.DateTimeField(_("started at"), null=True, blank=True)
    completed_at = models.DateTimeField(_("completed at"), null=True, blank=True)
    canceled_at = models.DateTimeField(_("canceled at"), null=True, blank=True)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("task")
        verbose_name_plural = _("tasks")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} [{self.status}]"

    @property
    def cenceled_at(self):
        return self.canceled_at

    @cenceled_at.setter
    def cenceled_at(self, value):
        self.canceled_at = value

    @property
    def description(self) -> str:
        return self.desc

    @description.setter
    def description(self, value: str):
        self.desc = value

    def save(self, *args, **kwargs):
        from django.utils import timezone

        now = timezone.now()
        # If clerk is assigned and status is PENDING, transition to ASSIGNED
        if self.clerk and self.status == TaskStatus.PENDING:
            self.status = TaskStatus.ASSIGNED

        # Auto-set timestamps based on status
        if self.status == TaskStatus.ASSIGNED and not self.assigned_at:
            self.assigned_at = now
        elif self.status == TaskStatus.STARTED:
            if not self.started_at:
                self.started_at = now
            if not self.assigned_at:
                self.assigned_at = now
        elif self.status == TaskStatus.COMPLETED:
            if not self.completed_at:
                self.completed_at = now
        elif self.status == TaskStatus.CANCELED:
            if not self.canceled_at:
                self.canceled_at = now
        super().save(*args, **kwargs)
