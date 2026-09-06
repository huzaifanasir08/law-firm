import uuid

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class UserRole(models.TextChoices):
    """Available roles within the Law Firm platform."""

    SUPER_ADMIN = "SUPER_ADMIN", _("Super Admin")
    FIRM_ADMIN = "FIRM_ADMIN", _("Firm Admin")
    LAWYER = "LAWYER", _("Lawyer")
    CLERK = "CLERK", _("Clerk")


class UserManager(BaseUserManager):
    """Custom manager for the email-based User model."""

    def create_user(self, email: str, password: str | None = None, **extra_fields):
        if not email:
            raise ValueError(_("Email address is required."))
        email = self.normalize_email(email)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("role", UserRole.CLERK)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("role", UserRole.SUPER_ADMIN)

        if extra_fields.get("is_staff") is not True:
            raise ValueError(_("Superuser must have is_staff=True."))
        if extra_fields.get("is_superuser") is not True:
            raise ValueError(_("Superuser must have is_superuser=True."))

        return self.create_user(email, password, **extra_fields)


def _profile_photo_upload_path(instance, filename: str) -> str:
    """Generate a unique upload path for profile photos."""
    ext = filename.rsplit(".", 1)[-1].lower()
    unique_name = f"{uuid.uuid4().hex}.{ext}"
    return f"profile_photos/{unique_name}"


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom user model for the Law Firm platform.

    Authenticates with email + password instead of username + password.
    """

    # ── Core identity ─────────────────────────────────────────────────────────
    name = models.CharField(_("full name"), max_length=255)
    email = models.EmailField(
        _("email address"),
        unique=True,
        db_index=True,
        error_messages={"unique": _("A user with that email already exists.")},
    )

    # ── Contact & location ────────────────────────────────────────────────────
    phone = models.CharField(_("phone number"), max_length=30, blank=True, default="")
    address = models.TextField(_("address"), blank=True, default="")

    # ── Role ──────────────────────────────────────────────────────────────────
    role = models.CharField(
        _("role"),
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.CLERK,
        db_index=True,
    )

    # ── Profile photo ─────────────────────────────────────────────────────────
    profile_photo = models.ImageField(
        _("profile photo"),
        upload_to=_profile_photo_upload_path,
        blank=True,
        null=True,
    )

    # ── Status flags ──────────────────────────────────────────────────────────
    is_active = models.BooleanField(
        _("active"),
        default=True,
        help_text=_(
            "Designates whether this user should be treated as active. "
            "Unselect this instead of deleting accounts."
        ),
    )
    is_staff = models.BooleanField(
        _("staff status"),
        default=False,
        help_text=_("Designates whether the user can log into the admin site."),
    )

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)
    # last_login is inherited from AbstractBaseUser

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name"]

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} <{self.email}>"

    @property
    def is_super_admin(self) -> bool:
        return self.role == UserRole.SUPER_ADMIN

    @property
    def is_firm_admin(self) -> bool:
        return self.role == UserRole.FIRM_ADMIN

    @property
    def is_lawyer(self) -> bool:
        return self.role == UserRole.LAWYER

    @property
    def is_clerk(self) -> bool:
        return self.role == UserRole.CLERK


class PasswordResetToken(models.Model):
    """
    A single-use, time-limited password reset token.

    The raw token is never stored — only its HMAC-SHA256 hash is persisted.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="password_reset_tokens",
        verbose_name=_("user"),
    )
    token_hash = models.CharField(
        _("token hash"),
        max_length=64,
        unique=True,
        db_index=True,
        help_text=_("HMAC-SHA256 hex digest of the raw token."),
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    expires_at = models.DateTimeField(_("expires at"))
    used = models.BooleanField(_("used"), default=False)

    class Meta:
        verbose_name = _("password reset token")
        verbose_name_plural = _("password reset tokens")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"PasswordResetToken(user={self.user.email}, used={self.used})"

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    @property
    def is_valid(self) -> bool:
        return not self.used and not self.is_expired
