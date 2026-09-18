"""
Serializers for the firm app.
"""

import logging
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.accounts.models import User, UserRole
from apps.administration.serializers import generate_secure_password
from .emails import send_lawyer_welcome_email
from .models import Firm, FirmType

logger = logging.getLogger(__name__)


class FirmSerializer(serializers.ModelSerializer):
    """Serializer for Firm details."""

    class Meta:
        model = Firm
        fields = [
            "id",
            "name",
            "type",
            "registration_number",
            "email",
            "phone",
            "address",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_type(self, value: str) -> str:
        if isinstance(value, str):
            value = value.upper()
        if value not in FirmType.values:
            raise serializers.ValidationError(
                _("Invalid firm type. Allowed types are: %(types)s") % {"types": ", ".join(FirmType.values)}
            )
        return value


class FirmLawyerSerializer(serializers.ModelSerializer):
    """Serializer for representing a lawyer user within a firm."""

    firm_id = serializers.PrimaryKeyRelatedField(source="firm", read_only=True)
    firm_name = serializers.CharField(source="firm.name", read_only=True)
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
            "firm_id",
            "firm_name",
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


class FirmCreateLawyerSerializer(serializers.ModelSerializer):
    """
    Serializer for creating a new lawyer associated with the firm.
    Generates a secure password and emails credentials to the lawyer.
    """

    email = serializers.EmailField()

    class Meta:
        model = User
        fields = ["id", "name", "email", "phone", "address"]
        read_only_fields = ["id"]
        extra_kwargs = {
            "phone": {"required": False, "default": ""},
            "address": {"required": False, "default": ""},
        }

    def validate(self, attrs: dict) -> dict:
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user and getattr(user, "firm", None) and user.firm.is_individual:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied(
                _("Firms with individual type cannot add or manage lawyers.")
            )
        return attrs

    def validate_email(self, value: str) -> str:
        email = value.lower().strip()
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError(_("A user with that email already exists."))
        return email

    def create(self, validated_data: dict) -> User:
        request = self.context.get("request")
        firm = getattr(request.user, "firm", None)
        if firm and firm.is_individual:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied(
                _("Firms with individual type cannot add or manage lawyers.")
            )
        if not firm:
            # If the user has no firm associated yet, get or create a default firm for this admin
            firm, _ = Firm.objects.get_or_create(
                name=f"{request.user.name}'s Firm",
                defaults={"email": request.user.email, "phone": request.user.phone},
            )
            request.user.firm = firm
            request.user.save(update_fields=["firm"])

        raw_password = generate_secure_password(14)

        lawyer = User.objects.create_user(
            email=validated_data["email"],
            password=raw_password,
            name=validated_data["name"],
            phone=validated_data.get("phone", ""),
            address=validated_data.get("address", ""),
            role=UserRole.LAWYER,
            firm=firm,
            is_active=True,
            is_staff=False,
            is_superuser=False,
        )

        try:
            send_lawyer_welcome_email(lawyer, raw_password, firm.name)
        except Exception:
            logger.exception("Failed to send welcome credentials email to lawyer %s", lawyer.email)

        return lawyer


class FirmUpdateLawyerSerializer(serializers.ModelSerializer):
    """Serializer for updating a lawyer's details."""

    class Meta:
        model = User
        fields = ["name", "phone", "address", "is_active"]
        extra_kwargs = {
            "name": {"required": False},
            "phone": {"required": False},
            "address": {"required": False},
            "is_active": {"required": False},
        }


class FirmStatsSerializer(serializers.Serializer):
    """Serializer for firm-level overview metrics."""

    total_lawyers = serializers.IntegerField(help_text="Total lawyers linked to this firm")
    active_lawyers = serializers.IntegerField(help_text="Total active lawyers linked to this firm")
    inactive_lawyers = serializers.IntegerField(help_text="Total inactive lawyers linked to this firm")
    total_matters = serializers.IntegerField(help_text="Total matters across all lawyers in this firm")
