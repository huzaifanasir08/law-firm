"""
Serializers for the matters app.
"""

from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.lawyer.models import Client
from .models import Matter, MatterPriority, MatterStatus


class MatterSerializer(serializers.ModelSerializer):
    """Serializer for managing legal matters."""

    client = serializers.PrimaryKeyRelatedField(queryset=Client.objects.all())
    client_name = serializers.CharField(source="client.name", read_only=True)
    lawyer_id = serializers.PrimaryKeyRelatedField(source="lawyer", read_only=True)
    lawyer_name = serializers.CharField(source="lawyer.name", read_only=True)
    firm_id = serializers.PrimaryKeyRelatedField(source="firm", read_only=True)
    firm_name = serializers.CharField(source="firm.name", read_only=True, default=None)

    class Meta:
        model = Matter
        fields = [
            "id",
            "title",
            "case_number",
            "description",
            "client",
            "client_name",
            "lawyer_id",
            "lawyer_name",
            "firm_id",
            "firm_name",
            "status",
            "priority",
            "due_date",
            "closed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "case_number",
            "client_name",
            "lawyer_id",
            "lawyer_name",
            "firm_id",
            "firm_name",
            "closed_at",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs: dict) -> dict:
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user and getattr(user, "role", None) == "FIRM_ADMIN":
            from apps.firm.views import _get_or_create_user_firm
            firm = _get_or_create_user_firm(user)
            if firm.is_multi:
                raise serializers.ValidationError(
                    _("Firms with multi type can only list matters, not add or manage them.")
                )
        return attrs

    def validate_client(self, value: Client) -> Client:
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if user and not user.is_superuser:
            if user.role == "LAWYER":
                if value.lawyer_id != user.id:
                    raise serializers.ValidationError(_("You can only assign matters to your own clients."))
            elif user.role == "FIRM_ADMIN":
                firm = getattr(user, "firm", None)
                if value.lawyer_id != user.id and not (firm and value.firm_id == firm.id):
                    raise serializers.ValidationError(_("You can only assign matters to your own clients."))
            else:
                if value.lawyer_id != user.id:
                    raise serializers.ValidationError(_("You can only assign matters to your own clients."))
        return value

    def create(self, validated_data: dict) -> Matter:
        request = self.context.get("request")
        user = getattr(request, "user", None)
        validated_data["lawyer"] = user
        if user:
            from apps.firm.views import _get_or_create_user_firm
            firm = _get_or_create_user_firm(user) if getattr(user, "role", None) == "FIRM_ADMIN" else user.firm
            if firm:
                validated_data["firm"] = firm
        if validated_data.get("status") == MatterStatus.CLOSED:
            validated_data["closed_at"] = timezone.now()
        return super().create(validated_data)

    def update(self, instance: Matter, validated_data: dict) -> Matter:
        new_status = validated_data.get("status", instance.status)
        if new_status == MatterStatus.CLOSED and instance.status != MatterStatus.CLOSED:
            validated_data["closed_at"] = timezone.now()
        elif new_status != MatterStatus.CLOSED and instance.status == MatterStatus.CLOSED:
            validated_data["closed_at"] = None
        return super().update(instance, validated_data)


class MatterStatsSerializer(serializers.Serializer):
    """Serializer for matter statistics scoped to a lawyer."""

    total_matters = serializers.IntegerField(help_text="Total matters assigned to lawyer")
    open_matters = serializers.IntegerField(help_text="Total open matters (open, in progress, pending)")
    closed_matters = serializers.IntegerField(help_text="Total closed matters")
    due_matters = serializers.IntegerField(help_text="Matters due on or before today and not closed")
    upcoming_matters = serializers.IntegerField(help_text="Matters due within the next 7 days and not closed")
