from django.contrib import admin
from .models import Client


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("name", "lawyer", "firm", "email", "phone", "role", "is_active", "created_at")
    list_filter = ("is_active", "role", "created_at", "firm")
    search_fields = ("name", "email", "phone", "lawyer__name", "lawyer__email")
    ordering = ("-created_at",)
