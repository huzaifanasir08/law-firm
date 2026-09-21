from django_filters import rest_framework as filters

from .models import (
    PaymentMethod,
    Plan,
    PlanCycle,
    Subscription,
    SubscriptionStatus,
    SubscriptionType,
    Transaction,
    TransactionStatus,
)


class PlanFilter(filters.FilterSet):
    cycle = filters.ChoiceFilter(choices=PlanCycle.choices)
    is_active = filters.BooleanFilter()
    is_public = filters.BooleanFilter()
    is_popular = filters.BooleanFilter()

    class Meta:
        model = Plan
        fields = ["cycle", "is_active", "is_public", "is_popular"]


class TransactionFilter(filters.FilterSet):
    status = filters.ChoiceFilter(choices=TransactionStatus.choices)
    payment_method = filters.ChoiceFilter(choices=PaymentMethod.choices)
    firm = filters.NumberFilter(field_name="firm__id")
    firm_admin = filters.NumberFilter(field_name="firm_admin__id")
    date_after = filters.DateTimeFilter(field_name="date", lookup_expr="gte")
    date_before = filters.DateTimeFilter(field_name="date", lookup_expr="lte")

    class Meta:
        model = Transaction
        fields = [
            "status",
            "payment_method",
            "firm",
            "firm_admin",
            "date_after",
            "date_before",
        ]


class SubscriptionFilter(filters.FilterSet):
    status = filters.ChoiceFilter(choices=SubscriptionStatus.choices)
    is_trial = filters.BooleanFilter()
    subscription_type = filters.ChoiceFilter(choices=SubscriptionType.choices)
    plan = filters.NumberFilter(field_name="plan__id")
    firm = filters.NumberFilter(field_name="firm__id")
    firm_admin = filters.NumberFilter(field_name="firm_admin__id")
    started_after = filters.DateTimeFilter(field_name="started_at", lookup_expr="gte")
    started_before = filters.DateTimeFilter(field_name="started_at", lookup_expr="lte")
    ends_after = filters.DateTimeFilter(field_name="ends_at", lookup_expr="gte")
    ends_before = filters.DateTimeFilter(field_name="ends_at", lookup_expr="lte")

    class Meta:
        model = Subscription
        fields = [
            "status",
            "is_trial",
            "subscription_type",
            "plan",
            "firm",
            "firm_admin",
            "started_after",
            "started_before",
            "ends_after",
            "ends_before",
        ]
