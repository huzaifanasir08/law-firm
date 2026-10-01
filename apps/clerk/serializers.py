"""
Serializers for the clerk app.
"""

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.accounts.models import User
from apps.lawyer.models import Task, TaskStatus


class ClerkTaskSerializer(serializers.ModelSerializer):
    """Serializer for tasks assigned to a clerk."""

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
        read_only_fields = fields


class ClerkTaskStatusUpdateSerializer(serializers.ModelSerializer):
    """Serializer for clerks updating their task lifecycle status."""

    status = serializers.CharField(required=True)

    class Meta:
        model = Task
        fields = ["status"]

    def validate_status(self, value: str) -> str:
        if isinstance(value, str):
            val_norm = value.upper().strip()
            if val_norm in ["CENCELED", "CENCELD", "CANCELLED", "CANCELED"]:
                val_norm = TaskStatus.CANCELED
            if val_norm in [TaskStatus.STARTED, TaskStatus.COMPLETED, TaskStatus.CANCELED]:
                return val_norm
        raise serializers.ValidationError(
            _("Clerks can only update status to STARTED, COMPLETED, or CANCELED.")
        )


class ClerkProfileSerializer(serializers.ModelSerializer):
    """Serializer for clerk's own profile."""

    firm_id = serializers.PrimaryKeyRelatedField(source="firm", read_only=True)
    firm_name = serializers.CharField(source="firm.name", read_only=True, default=None)
    lawyer_id = serializers.PrimaryKeyRelatedField(source="lawyer", read_only=True)
    lawyer_name = serializers.CharField(source="lawyer.name", read_only=True, default=None)
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
