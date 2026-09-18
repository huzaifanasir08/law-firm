from django.contrib import admin
from .models import Firm


@admin.register(Firm)
class FirmAdmin(admin.ModelAdmin):
    list_display = ("name", "type", "registration_number", "email", "phone", "is_active", "created_at")
    list_filter = ("type", "is_active", "created_at")
    search_fields = ("name", "registration_number", "email", "phone")
    ordering = ("-created_at",)
