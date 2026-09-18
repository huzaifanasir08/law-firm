from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import OTP, PasswordResetToken, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin configuration for the custom User model."""

    # ── List view ─────────────────────────────────────────────────────────────
    list_display = ("email", "name", "role", "is_active", "two_factor_enabled", "is_staff", "created_at")
    list_filter = ("role", "is_active", "two_factor_enabled", "is_staff", "is_superuser")
    search_fields = ("email", "name", "phone")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at", "last_login")

    # ── Detail view ───────────────────────────────────────────────────────────
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            _("Personal info"),
            {"fields": ("name", "phone", "address", "profile_photo")},
        ),
        (
            _("Role & Permissions"),
            {
                "fields": (
                    "role",
                    "two_factor_enabled",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        (
            _("Important dates"),
            {"fields": ("last_login", "created_at", "updated_at")},
        ),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "name", "role", "two_factor_enabled", "password1", "password2"),
            },
        ),
    )

    # The base UserAdmin uses 'username' — override to use 'email'
    filter_horizontal = ("groups", "user_permissions")


@admin.register(PasswordResetToken)
class PasswordResetTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "created_at", "expires_at", "used", "is_expired")
    list_filter = ("used",)
    search_fields = ("user__email",)
    readonly_fields = ("token_hash", "created_at", "expires_at", "user")

    @admin.display(boolean=True, description="Expired?")
    def is_expired(self, obj):
        return obj.is_expired


@admin.register(OTP)
class OTPAdmin(admin.ModelAdmin):
    list_display = ("user", "purpose", "created_at", "expires_at", "used", "attempts", "is_valid")
    list_filter = ("purpose", "used")
    search_fields = ("user__email",)
    readonly_fields = ("code_hash", "created_at", "expires_at", "user", "attempts")

    @admin.display(boolean=True, description="Valid?")
    def is_valid(self, obj):
        return obj.is_valid

