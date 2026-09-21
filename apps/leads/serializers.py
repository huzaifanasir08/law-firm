from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from .models import (
    Lead,
    LeadContactWay,
    LeadInterest,
    LeadInterestedFirm,
    LeadPreferredTime,
    LeadStatus,
)


def _normalize_lead_data(data) -> dict:
    """Normalize user input before DRF choice validation runs."""
    if hasattr(data, "dict"):
        data = data.dict()
    elif hasattr(data, "copy"):
        data = data.copy()
    else:
        data = dict(data)

    if "interest" in data and isinstance(data["interest"], str):
        val = data["interest"].strip().lower()
        if val in ["inqury", "inquiry"]:
            data["interest"] = LeadInterest.INQUIRY
        elif val == "register":
            data["interest"] = LeadInterest.REGISTER
        elif val == "other":
            data["interest"] = LeadInterest.OTHER

    if "interested_firm" in data and isinstance(data["interested_firm"], str):
        val = data["interested_firm"].strip().lower()
        if val in ["indvidual", "individual"]:
            data["interested_firm"] = LeadInterestedFirm.INDIVIDUAL
        elif val == "multi":
            data["interested_firm"] = LeadInterestedFirm.MULTI

    if "preferred_contact_way" in data and isinstance(data["preferred_contact_way"], str):
        val = data["preferred_contact_way"].strip().lower().replace(" ", "_")
        if val in ["phone_call", "phonecall", "phone"]:
            data["preferred_contact_way"] = LeadContactWay.PHONE_CALL
        elif val == "whatsapp":
            data["preferred_contact_way"] = LeadContactWay.WHATSAPP

    if "status" in data and isinstance(data["status"], str):
        val = data["status"].strip().lower().replace(" ", "_")
        if val in ["meeting_scheduled", "meetingscheduled"]:
            data["status"] = LeadStatus.MEETING_SCHEDULED
        elif val == "pending":
            data["status"] = LeadStatus.PENDING
        elif val == "contacted":
            data["status"] = LeadStatus.CONTACTED
        elif val == "confirmed":
            data["status"] = LeadStatus.CONFIRMED

    if "preferred_time" in data and isinstance(data["preferred_time"], str):
        val = data["preferred_time"].strip().lower()
        if val in ["8-10", "08-10"]:
            data["preferred_time"] = LeadPreferredTime.TIME_8_10

    return data


class PublicLeadCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for public lead registration / inquiry submission.
    """

    class Meta:
        model = Lead
        fields = [
            "id",
            "name",
            "email",
            "phone",
            "address",
            "interest",
            "interested_firm",
            "preferred_time",
            "preferred_contact_way",
            "status",
            "created_at",
        ]
        read_only_fields = ["id", "status", "created_at"]

    def to_internal_value(self, data):
        normalized = _normalize_lead_data(data)
        return super().to_internal_value(normalized)

    def validate_email(self, value: str) -> str:
        normalized_email = value.strip().lower()
        if Lead.objects.filter(email__iexact=normalized_email).exists():
            raise serializers.ValidationError(_("A lead with this email address already exists."))
        return normalized_email

    def create(self, validated_data):
        # Public submissions always start in PENDING status
        validated_data["status"] = LeadStatus.PENDING
        return super().create(validated_data)


class AdminLeadSerializer(serializers.ModelSerializer):
    """
    Serializer for admin views showing all lead details and workflow status.
    """

    class Meta:
        model = Lead
        fields = [
            "id",
            "name",
            "email",
            "phone",
            "address",
            "interest",
            "interested_firm",
            "status",
            "preferred_time",
            "preferred_contact_way",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class AdminLeadUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for Super Admins to edit lead details, status, and internal notes.
    """

    class Meta:
        model = Lead
        fields = [
            "id",
            "name",
            "email",
            "phone",
            "address",
            "interest",
            "interested_firm",
            "status",
            "preferred_time",
            "preferred_contact_way",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
        extra_kwargs = {
            "name": {"required": False},
            "email": {"required": False},
            "phone": {"required": False},
            "interest": {"required": False},
            "interested_firm": {"required": False},
            "preferred_time": {"required": False},
            "preferred_contact_way": {"required": False},
        }

    def to_internal_value(self, data):
        normalized = _normalize_lead_data(data)
        return super().to_internal_value(normalized)

    def validate_email(self, value: str) -> str:
        normalized_email = value.strip().lower()
        existing = Lead.objects.filter(email__iexact=normalized_email)
        if self.instance:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise serializers.ValidationError(_("A lead with this email address already exists."))
        return normalized_email
