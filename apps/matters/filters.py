"""
Filters for the matters app.
"""

import django_filters
from .models import Matter, MatterPriority, MatterStatus


class MatterFilter(django_filters.FilterSet):
    """Filter set for legal matters."""

    status = django_filters.ChoiceFilter(choices=MatterStatus.choices)
    priority = django_filters.ChoiceFilter(choices=MatterPriority.choices)
    client = django_filters.NumberFilter(field_name="client_id")
    due_date = django_filters.DateFilter(field_name="due_date")
    due_before = django_filters.DateFilter(field_name="due_date", lookup_expr="lte")
    due_after = django_filters.DateFilter(field_name="due_date", lookup_expr="gte")
    is_due = django_filters.BooleanFilter(method="filter_is_due")

    class Meta:
        model = Matter
        fields = ["status", "priority", "client", "due_date", "due_before", "due_after", "is_due"]

    def filter_is_due(self, queryset, name, value):
        from django.utils import timezone
        today = timezone.now().date()
        if value:
            return queryset.filter(due_date__lte=today).exclude(status=MatterStatus.CLOSED)
        return queryset
