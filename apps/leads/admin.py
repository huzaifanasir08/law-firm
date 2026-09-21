from django.contrib import admin

from .models import Lead


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "email",
        "phone",
        "interest",
        "interested_firm",
        "status",
        "preferred_time",
        "preferred_contact_way",
        "created_at",
    ]
    list_filter = [
        "status",
        "interest",
        "interested_firm",
        "preferred_contact_way",
        "preferred_time",
        "created_at",
    ]
    search_fields = ["name", "email", "phone", "address", "notes"]
    ordering = ["-created_at"]
    readonly_fields = ["created_at", "updated_at"]
