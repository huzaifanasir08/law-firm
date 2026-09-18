"""
Serializers for the administration app.
"""

import logging
import secrets
import string

from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.accounts.models import User, UserRole
from apps.firm.models import Firm, FirmType
from .emails import send_admin_user_welcome_email

logger = logging.getLogger(__name__)


def generate_secure_password(length: int = 14) -> str:
    """Generate a strong random password meeting all policy constraints."""
    upper = string.ascii_uppercase
    lower = string.ascii_lowercase
    digits = string.digits
    special = "!@#$%^&*()-_=+"
    all_chars = upper + lower + digits + special

    password_chars = [
        secrets.choice(upper),
        secrets.choice(lower),
        secrets.choice(digits),
        secrets.choice(special),
    ]
    password_chars += [secrets.choice(all_chars) for _ in range(length - 4)]
    secrets.SystemRandom().shuffle(password_chars)
    return "".join(password_chars)


class AdminUserSerializer(serializers.ModelSerializer):
    """Serializer for user records in admin views."""

    profile_photo = serializers.SerializerMethodField()
    firm_id = serializers.PrimaryKeyRelatedField(source="firm", read_only=True)
    firm_name = serializers.CharField(source="firm.name", read_only=True, default=None)
    firm_type = serializers.CharField(source="firm.type", read_only=True, default=None)

    class Meta:
        model = User
        fields = [
            "id",
            "name",
            "email",
            "phone",
            "address",
            "role",
            "firm_id",
            "firm_name",
            "firm_type",
            "profile_photo",
            "is_active",
            "is_staff",
            "is_superuser",
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


class AdminCreateUserSerializer(serializers.ModelSerializer):
    """
    Serializer for creating users by administrators.

    Super Admins may create Super Admin and Firm Admin roles.
    Firm Admins may create Firm Admin roles only.
    Generates a secure password and emails it to the user.
    """

    email = serializers.EmailField()
    role = serializers.ChoiceFilter() if False else serializers.ChoiceField(choices=UserRole.choices)
    firm_id = serializers.PrimaryKeyRelatedField(
        queryset=Firm.objects.all(), required=False, allow_null=True
    )
    firm_type = serializers.ChoiceField(
        choices=FirmType.choices, required=False
    )
    firm_name = serializers.CharField(
        required=False, max_length=255
    )

    class Meta:
        model = User
        fields = [
            "id",
            "name",
            "email",
            "phone",
            "address",
            "role",
            "is_active",
            "firm_id",
            "firm_type",
            "firm_name",
        ]
        read_only_fields = ["id"]
        extra_kwargs = {
            "phone": {"required": False, "default": ""},
            "address": {"required": False, "default": ""},
            "is_active": {"required": False, "default": True},
        }

    def validate_email(self, value: str) -> str:
        email = value.lower().strip()
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError(_("A user with that email already exists."))
        return email

    def validate_role(self, value: str) -> str:
        request = self.context.get("request")
        requester = getattr(request, "user", None)

        if value == UserRole.FIRM_ADMIN:
            raise serializers.ValidationError(
                _("Creating Law Firm Admins from this endpoint is not allowed.")
            )

        if requester and requester.role == UserRole.SUPER_ADMIN:
            if value != UserRole.SUPER_ADMIN:
                raise serializers.ValidationError(
                    _("Super Admin can only create users with role Super Admin from this endpoint.")
                )
        elif requester and requester.role == UserRole.FIRM_ADMIN:
            raise serializers.ValidationError(
                _("Firm Admin cannot create users from this endpoint.")
            )
        else:
            raise serializers.ValidationError(_("You do not have permission to create users."))

        return value

    def create(self, validated_data: dict) -> User:
        raw_password = generate_secure_password(14)
        role = validated_data.get("role", UserRole.SUPER_ADMIN)
        if role == UserRole.FIRM_ADMIN:
            raise serializers.ValidationError(
                _("Creating Law Firm Admins from this endpoint is not allowed.")
            )
        is_superuser = role == UserRole.SUPER_ADMIN
        is_staff = role in [UserRole.SUPER_ADMIN, UserRole.FIRM_ADMIN]

        firm = validated_data.get("firm_id")
        firm_type = validated_data.get("firm_type")
        firm_name = validated_data.get("firm_name")

        if not firm and (firm_type or firm_name):
            firm = Firm.objects.create(
                name=firm_name or f"{validated_data['name']}'s Firm",
                type=firm_type or FirmType.MULTI,
                email=validated_data["email"],
                phone=validated_data.get("phone", ""),
            )

        user = User.objects.create_user(
            email=validated_data["email"],
            password=raw_password,
            name=validated_data["name"],
            phone=validated_data.get("phone", ""),
            address=validated_data.get("address", ""),
            role=role,
            firm=firm,
            is_active=validated_data.get("is_active", True),
            is_staff=is_staff,
            is_superuser=is_superuser,
        )

        try:
            send_admin_user_welcome_email(user, raw_password)
        except Exception:
            logger.exception("Failed to send welcome email to newly created user %s", user.email)

        return user



class AdminUserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating user details in admin views."""

    class Meta:
        model = User
        fields = ["name", "phone", "address", "role", "is_active"]
        extra_kwargs = {
            "name": {"required": False},
            "phone": {"required": False},
            "address": {"required": False},
            "role": {"required": False},
            "is_active": {"required": False},
        }

    def validate_role(self, value: str) -> str:
        request = self.context.get("request")
        requester = getattr(request, "user", None)

        if requester and requester.role == UserRole.FIRM_ADMIN:
            if value == UserRole.SUPER_ADMIN:
                raise serializers.ValidationError(_("Firm Admin cannot promote users to Super Admin."))

        return value

    def validate(self, attrs: dict) -> dict:
        instance: User = self.instance
        # Prevent deactivating the last active super admin
        if instance and instance.role == UserRole.SUPER_ADMIN:
            new_role = attrs.get("role", instance.role)
            new_is_active = attrs.get("is_active", instance.is_active)
            if (new_role != UserRole.SUPER_ADMIN or not new_is_active) and instance.is_active:
                active_super_admins = User.objects.filter(
                    role=UserRole.SUPER_ADMIN, is_active=True
                ).exclude(id=instance.id).count()
                if active_super_admins == 0:
                    raise serializers.ValidationError(
                        _("Cannot deactivate or demote the last active Super Admin.")
                    )
        return attrs


class AdminStatsSerializer(serializers.Serializer):
    """Serializer for administrative statistics overview."""

    total_users = serializers.IntegerField(help_text="Total registered users")
    total_active_users = serializers.IntegerField(help_text="Total active users")
    users_this_month = serializers.IntegerField(help_text="Users registered in current month")
    users_last_month = serializers.IntegerField(help_text="Users registered in previous month")
    total_firm_admins = serializers.IntegerField(help_text="Total Firm Admin users")
    total_lawyers = serializers.IntegerField(help_text="Total Lawyer users")
