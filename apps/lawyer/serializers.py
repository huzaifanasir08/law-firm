"""
Serializers for the lawyer app.
"""

from rest_framework import serializers

from .models import Client


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
