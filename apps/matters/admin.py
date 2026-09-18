from django.contrib import admin
from .models import Matter


@admin.register(Matter)
class MatterAdmin(admin.ModelAdmin):
    list_display = ("case_number", "title", "lawyer", "client", "firm", "status", "priority", "due_date", "created_at")
    list_filter = ("status", "priority", "created_at", "firm")
    search_fields = ("case_number", "title", "description", "lawyer__name", "client__name")
    ordering = ("-created_at",)
