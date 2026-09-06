"""
Serializers for the accounts app.
"""

from io import BytesIO

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.translation import gettext_lazy as _
from PIL import Image
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User


# ─── User Profile ─────────────────────────────────────────────────────────────


class UserProfileSerializer(serializers.ModelSerializer):
    """Read-only serializer for user profile data. Never exposes passwords."""

    profile_photo = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "name",
            "email",
            "phone",
            "address",
            "role",
            "profile_photo",
            "is_active",
            "created_at",
            "updated_at",
            "last_login",
        ]
        read_only_fields = fields

    def get_profile_photo(self, obj: User) -> str | None:
        if not obj.profile_photo:
            return None
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(obj.profile_photo.url)
        return obj.profile_photo.url


class UserProfileMiniSerializer(serializers.ModelSerializer):
    """Minimal profile returned alongside auth tokens."""

    profile_photo = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "name", "email", "phone", "address", "role", "profile_photo"]
        read_only_fields = fields

    def get_profile_photo(self, obj: User) -> str | None:
        if not obj.profile_photo:
            return None
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(obj.profile_photo.url)
        return obj.profile_photo.url


# ─── Authentication ───────────────────────────────────────────────────────────


class LoginSerializer(serializers.Serializer):
    """Validate email/password and return JWT tokens + user profile."""

    email = serializers.EmailField(write_only=True)
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate(self, attrs: dict) -> dict:
        email = attrs.get("email", "").lower().strip()
        password = attrs.get("password", "")

        user = authenticate(
            request=self.context.get("request"),
            username=email,
            password=password,
        )
        if user is None:
            # Generic message — do not reveal whether email or password is wrong
            raise serializers.ValidationError(
                {"non_field_errors": [_("Invalid credentials. Please try again.")]},
                code="authentication_failed",
            )

        if not user.is_active:
            raise serializers.ValidationError(
                {"non_field_errors": [_("This account has been deactivated.")]},
                code="account_inactive",
            )

        refresh = RefreshToken.for_user(user)
        return {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": user,
        }


# ─── Logout ───────────────────────────────────────────────────────────────────


class LogoutSerializer(serializers.Serializer):
    """Accept a refresh token for blacklisting."""

    refresh = serializers.CharField(write_only=True, help_text="The refresh token to invalidate.")


# ─── Change Password ──────────────────────────────────────────────────────────


class ChangePasswordSerializer(serializers.Serializer):
    """Validate current and new passwords for the authenticated user."""

    old_password = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
        help_text="The user's current password.",
    )
    new_password = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
        help_text="The desired new password.",
    )

    def validate_old_password(self, value: str) -> str:
        user: User = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError(_("Current password is incorrect."))
        return value

    def validate_new_password(self, value: str) -> str:
        user: User = self.context["request"].user
        try:
            validate_password(value, user=user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return value

    def validate(self, attrs: dict) -> dict:
        if attrs.get("old_password") == attrs.get("new_password"):
            raise serializers.ValidationError(
                {"new_password": [_("New password must differ from the current password.")]}
            )
        return attrs


# ─── Forgot Password ──────────────────────────────────────────────────────────


class ForgotPasswordSerializer(serializers.Serializer):
    """Accept an email address to trigger a password-reset flow."""

    email = serializers.EmailField()


# ─── Reset Password ───────────────────────────────────────────────────────────


class ResetPasswordSerializer(serializers.Serializer):
    """Accept a reset token and a new password."""

    token = serializers.CharField(
        write_only=True,
        help_text="The password-reset token received by email.",
    )
    new_password = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
        help_text="The desired new password.",
    )

    def validate_new_password(self, value: str) -> str:
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return value


# ─── Profile Photo ────────────────────────────────────────────────────────────


class ProfilePhotoSerializer(serializers.ModelSerializer):
    """Validate and store a user profile photo."""

    class Meta:
        model = User
        fields = ["profile_photo"]

    def validate_profile_photo(self, value):
        max_size_mb: int = getattr(settings, "PROFILE_PHOTO_MAX_SIZE_MB", 5)
        allowed_formats: set[str] = {"JPEG", "PNG", "GIF", "WEBP"}

        # Size check
        if value.size > max_size_mb * 1024 * 1024:
            raise serializers.ValidationError(
                _(f"Profile photo must not exceed {max_size_mb} MB.")
            )

        # Content detection via Pillow (reads file header, not Content-Type)
        try:
            image = Image.open(BytesIO(value.read()))
            image.verify()  # Ensures the file is a valid image
            detected_format = image.format
            value.seek(0)  # Reset file pointer after reading
        except Exception:
            value.seek(0)
            raise serializers.ValidationError(
                _("Uploaded file is not a valid image.")
            )

        if detected_format not in allowed_formats:
            raise serializers.ValidationError(
                _("Unsupported file type. Allowed types: JPEG, PNG, GIF, WEBP.")
            )

        return value
