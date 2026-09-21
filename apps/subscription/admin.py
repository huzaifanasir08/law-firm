from django.contrib import admin

from .models import Plan, Subscription, Transaction


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ["name", "price", "cycle", "is_active", "is_public", "is_popular", "created_at"]
    list_filter = ["cycle", "is_active", "is_public", "is_popular"]
    search_fields = ["name", "description"]


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = [
        "transaction_id",
        "amount",
        "status",
        "payment_method",
        "firm",
        "firm_admin",
        "date",
    ]
    list_filter = ["status", "payment_method", "date"]
    search_fields = [
        "transaction_id",
        "firm__name",
        "firm_admin__email",
        "sender_bank_account",
        "receiver_bank_account",
    ]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = [
        "firm",
        "plan",
        "status",
        "is_trial",
        "subscription_type",
        "started_at",
        "ends_at",
        "created_at",
    ]
    list_filter = ["status", "is_trial", "subscription_type", "plan"]
    search_fields = ["firm__name", "firm_admin__email", "plan__name"]
    readonly_fields = ["created_at", "updated_at"]
