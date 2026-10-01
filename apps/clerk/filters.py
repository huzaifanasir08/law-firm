"""
Filters for the clerk app.
"""

from django_filters import rest_framework as filters

from apps.lawyer.models import Task, TaskStatus


class ClerkTaskFilter(filters.FilterSet):
    """FilterSet for clerk tasks."""

    status = filters.ChoiceFilter(choices=TaskStatus.choices)
    name = filters.CharFilter(lookup_expr="icontains")
    created_after = filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before = filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="lte")

    class Meta:
        model = Task
        fields = ["status", "name", "created_after", "created_before"]
