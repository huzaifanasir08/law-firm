"""
Filter sets for administration endpoints.
"""

from django_filters import rest_framework as filters

from apps.accounts.models import User, UserRole


class UserAdminFilter(filters.FilterSet):
    role = filters.ChoiceFilter(choices=UserRole.choices)
    is_active = filters.BooleanFilter()
    created_after = filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before = filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")

    class Meta:
        model = User
        fields = ["role", "is_active", "created_after", "created_before"]
