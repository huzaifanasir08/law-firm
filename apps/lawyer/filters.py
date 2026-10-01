"""
Filters for the lawyer app.
"""

import django_filters
from apps.accounts.models import User
from .models import Client, Task, TaskStatus


class LawyerClientFilter(django_filters.FilterSet):
    """Filter set for clients belonging to a lawyer."""

    is_active = django_filters.BooleanFilter(field_name="is_active")
    created_after = django_filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before = django_filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="lte")

    class Meta:
        model = Client
        fields = ["is_active", "created_after", "created_before"]


class LawyerTaskFilter(django_filters.FilterSet):
    """Filter set for tasks belonging to a lawyer."""

    status = django_filters.ChoiceFilter(choices=TaskStatus.choices)
    clerk = django_filters.NumberFilter(field_name="clerk__id")
    name = django_filters.CharFilter(lookup_expr="icontains")
    created_after = django_filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before = django_filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="lte")

    class Meta:
        model = Task
        fields = ["status", "clerk", "name", "created_after", "created_before"]


class LawyerClerkFilter(django_filters.FilterSet):
    """Filter set for clerks associated with a lawyer."""

    is_active = django_filters.BooleanFilter(field_name="is_active")
    name = django_filters.CharFilter(lookup_expr="icontains")
    email = django_filters.CharFilter(lookup_expr="icontains")
    created_after = django_filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before = django_filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="lte")

    class Meta:
        model = User
        fields = ["is_active", "name", "email", "created_after", "created_before"]

