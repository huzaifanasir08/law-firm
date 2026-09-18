"""
Filters for the firm app.
"""

import django_filters
from apps.accounts.models import User


class FirmLawyerFilter(django_filters.FilterSet):
    """Filter set for lawyers within a firm."""

    is_active = django_filters.BooleanFilter(field_name="is_active")
    created_after = django_filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before = django_filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="lte")

    class Meta:
        model = User
        fields = ["is_active", "created_after", "created_before"]
