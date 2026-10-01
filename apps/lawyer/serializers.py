import logging
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.accounts.models import User, UserRole
from apps.administration.serializers import generate_secure_password
from apps.clerk.emails import send_clerk_welcome_email
from .models import Client, Task, TaskStatus

logger = logging.getLogger(__name__)


class ClientSerializer(serializers.ModelSerializer):
    """Serializer for client records managed by a lawyer."""

    lawyer_id = serializers.PrimaryKeyRelatedField(source="lawyer", read_only=True)
    lawyer_name = serializers.CharField(source="lawyer.name", read_only=True)
    firm_id = serializers.PrimaryKeyRelatedField(source="firm", read_only=True)
    firm_name = serializers.CharField(source="firm.name", read_only=True, default=None)
    total_matters = serializers.SerializerMethodField()

    class Meta:
        model = Client
        fields = [
            "id",
            "name",
            "email",
            "phone",
            "address",
            "role",
            "is_active",
            "notes",
            "lawyer_id",
            "lawyer_name",
            "firm_id",
            "firm_name",
            "total_matters",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "role", "lawyer_id", "lawyer_name", "firm_id", "firm_name", "created_at", "updated_at"]

    def get_total_matters(self, obj: Client) -> int:
        return obj.matters.count()

    def validate(self, attrs: dict) -> dict:
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user and getattr(user, "role", None) == "FIRM_ADMIN":
            from apps.firm.views import _get_or_create_user_firm
            firm = _get_or_create_user_firm(user)
            if firm.is_multi:
                raise serializers.ValidationError(
                    _("Firms with multi type can only list clients, not add or manage them.")
                )
        return attrs

    def create(self, validated_data: dict) -> Client:
        request = self.context.get("request")
        user = getattr(request, "user", None)
        validated_data["lawyer"] = user
        if user:
            from apps.firm.views import _get_or_create_user_firm
            firm = _get_or_create_user_firm(user) if user.role == "FIRM_ADMIN" else user.firm
            if firm:
                validated_data["firm"] = firm
        return super().create(validated_data)



class ClientUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating client details."""

    class Meta:
        model = Client
        fields = ["name", "email", "phone", "address", "is_active", "notes"]
        extra_kwargs = {
            "name": {"required": False},
            "email": {"required": False},
            "phone": {"required": False},
            "address": {"required": False},
            "is_active": {"required": False},
            "notes": {"required": False},
        }


class ClientStatsSerializer(serializers.Serializer):
    """Serializer for lawyer client statistics."""

    total_clients = serializers.IntegerField(help_text="Total clients assigned to the lawyer")
    active_clients = serializers.IntegerField(help_text="Total active clients")
    inactive_clients = serializers.IntegerField(help_text="Total inactive clients")
    total_matters = serializers.IntegerField(help_text="Total matters across all clients of this lawyer")


class TaskSerializer(serializers.ModelSerializer):
    """Serializer for tasks managed by a lawyer."""

    lawyer_id = serializers.PrimaryKeyRelatedField(source="lawyer", read_only=True)
    lawyer_name = serializers.CharField(source="lawyer.name", read_only=True)
    clerk_id = serializers.PrimaryKeyRelatedField(source="clerk", read_only=True)
    clerk_name = serializers.CharField(source="clerk.name", read_only=True, default=None)
    firm_id = serializers.PrimaryKeyRelatedField(source="firm", read_only=True)
    firm_name = serializers.CharField(source="firm.name", read_only=True, default=None)
    cenceled_at = serializers.DateTimeField(source="canceled_at", read_only=True)

    class Meta:
        model = Task
        fields = [
            "id",
            "name",
            "desc",
            "status",
            "lawyer_id",
            "lawyer_name",
            "clerk_id",
            "clerk_name",
            "firm_id",
            "firm_name",
            "assigned_at",
            "started_at",
            "completed_at",
            "canceled_at",
            "cenceled_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "lawyer_id",
            "lawyer_name",
            "clerk_id",
            "clerk_name",
            "firm_id",
            "firm_name",
            "assigned_at",
            "started_at",
            "completed_at",
            "canceled_at",
            "cenceled_at",
            "created_at",
            "updated_at",
        ]


class TaskCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a new task by a lawyer."""

    clerk = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role=UserRole.CLERK),
        required=False,
        allow_null=True,
    )
    status = serializers.CharField(required=False, default=TaskStatus.PENDING)

    class Meta:
        model = Task
        fields = ["id", "name", "desc", "clerk", "status"]
        read_only_fields = ["id"]

    def validate_status(self, value: str) -> str:
        if isinstance(value, str):
            val_norm = value.upper().strip()
            if val_norm in ["CENCELED", "CENCELD", "CANCELLED", "CANCELED"]:
                return TaskStatus.CANCELED
            if val_norm in TaskStatus.values:
                return val_norm
        raise serializers.ValidationError(_("Invalid task status."))

    def validate_clerk(self, value: User | None) -> User | None:
        if not value:
            return None
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user and value.role != UserRole.CLERK:
            raise serializers.ValidationError(_("Selected user is not a clerk."))
        return value

    def create(self, validated_data: dict) -> Task:
        request = self.context.get("request")
        user = getattr(request, "user", None)
        validated_data["lawyer"] = user
        if user:
            from apps.firm.views import _get_or_create_user_firm

            firm = _get_or_create_user_firm(user) if user.role == UserRole.FIRM_ADMIN else user.firm
            if firm:
                validated_data["firm"] = firm

        return super().create(validated_data)


class TaskUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating a task by a lawyer."""

    clerk = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role=UserRole.CLERK),
        required=False,
        allow_null=True,
    )
    status = serializers.CharField(required=False)

    class Meta:
        model = Task
        fields = ["name", "desc", "clerk", "status"]
        extra_kwargs = {
            "name": {"required": False},
            "desc": {"required": False},
        }

    def validate_status(self, value: str) -> str:
        if isinstance(value, str):
            val_norm = value.upper().strip()
            if val_norm in ["CENCELED", "CENCELD", "CANCELLED", "CANCELED"]:
                return TaskStatus.CANCELED
            if val_norm in TaskStatus.values:
                return val_norm
        raise serializers.ValidationError(_("Invalid task status."))



class LawyerClerkSerializer(serializers.ModelSerializer):
    """Serializer for representing a clerk user managed by a lawyer."""

    firm_id = serializers.PrimaryKeyRelatedField(source="firm", read_only=True)
    firm_name = serializers.CharField(source="firm.name", read_only=True, default=None)
    lawyer_id = serializers.PrimaryKeyRelatedField(source="lawyer", read_only=True)
    lawyer_name = serializers.CharField(source="lawyer.name", read_only=True, default=None)
    total_tasks = serializers.SerializerMethodField()
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
            "lawyer_id",
            "lawyer_name",
            "profile_photo",
            "is_active",
            "total_tasks",
            "created_at",
            "updated_at",
            "last_login",
        ]
        read_only_fields = fields

    def get_total_tasks(self, obj: User) -> int:
        return obj.clerk_tasks.count()

    def get_profile_photo(self, obj: User) -> str | None:
        if not obj.profile_photo:
            return None
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(obj.profile_photo.url)
        return obj.profile_photo.url


class LawyerCreateClerkSerializer(serializers.ModelSerializer):
    """
    Serializer for creating a new clerk associated with the authenticated lawyer.
    Generates a secure password and emails credentials to the clerk.
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

    def validate_email(self, value: str) -> str:
        email = value.lower().strip()
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError(_("A user with that email already exists."))
        return email

    def create(self, validated_data: dict) -> User:
        request = self.context.get("request")
        lawyer = request.user
        firm = lawyer.firm
        if not firm and lawyer.role == UserRole.FIRM_ADMIN:
            from apps.firm.views import _get_or_create_user_firm

            firm = _get_or_create_user_firm(lawyer)

        raw_password = generate_secure_password(14)

        clerk = User.objects.create_user(
            email=validated_data["email"],
            password=raw_password,
            name=validated_data["name"],
            phone=validated_data.get("phone", ""),
            address=validated_data.get("address", ""),
            role=UserRole.CLERK,
            lawyer=lawyer,
            firm=firm,
            is_active=True,
            is_staff=False,
            is_superuser=False,
        )

        firm_name = firm.name if firm else f"{lawyer.name}'s Practice"
        try:
            send_clerk_welcome_email(
                clerk,
                raw_password,
                firm_name=firm_name,
                lawyer_name=lawyer.name,
            )
        except Exception:
            logger.exception("Failed to send welcome credentials email to clerk %s", clerk.email)

        return clerk


class LawyerUpdateClerkSerializer(serializers.ModelSerializer):
    """Serializer for updating a clerk's profile details by a lawyer."""

    class Meta:
        model = User
        fields = ["name", "phone", "address", "is_active"]
        extra_kwargs = {
            "name": {"required": False},
            "phone": {"required": False},
            "address": {"required": False},
            "is_active": {"required": False},
        }

