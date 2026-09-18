"""
Filters for the lawyer app.
"""

import django_filters
from .models import Client


class LawyerClientFilter(django_filters.FilterSet):
    """Filter set for clients belonging to a lawyer."""

    is_active = django_filters.BooleanFilter(field_name="is_active")
    created_after = django_filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before = django_filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="lte")

    class Meta:
        model = Client
        fields = ["is_active", "created_after", "created_before"]
