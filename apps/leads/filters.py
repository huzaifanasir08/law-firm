from django_filters import rest_framework as filters

from .models import (
    Lead,
    LeadContactWay,
    LeadInterest,
    LeadInterestedFirm,
    LeadPreferredTime,
    LeadStatus,
)


class LeadFilter(filters.FilterSet):
    """
    Filter set for leads querysets.
    """

    status = filters.ChoiceFilter(choices=LeadStatus.choices)
    interest = filters.ChoiceFilter(choices=LeadInterest.choices)
    interested_firm = filters.ChoiceFilter(choices=LeadInterestedFirm.choices)
    preferred_time = filters.ChoiceFilter(choices=LeadPreferredTime.choices)
    preferred_contact_way = filters.ChoiceFilter(choices=LeadContactWay.choices)
    created_after = filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before = filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")

    class Meta:
        model = Lead
        fields = [
            "status",
            "interest",
            "interested_firm",
            "preferred_time",
            "preferred_contact_way",
            "created_after",
            "created_before",
        ]
