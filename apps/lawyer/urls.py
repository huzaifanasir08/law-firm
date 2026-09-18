"""
URL configuration for the lawyer app.
"""

from django.urls import path

from apps.matters.views import (
    LawyerMatterDetailView,
    LawyerMatterListCreateView,
    LawyerMatterStatsView,
)
from .views import (
    LawyerClientDetailView,
    LawyerClientListCreateView,
    LawyerClientReactivateView,
    LawyerClientStatsView,
    LawyerOverviewStatsView,
)

urlpatterns = [
    # Client management
    path("clients/", LawyerClientListCreateView.as_view(), name="lawyer-clients-list-create"),
    path("clients/<int:pk>/", LawyerClientDetailView.as_view(), name="lawyer-client-detail"),
    path("clients/<int:pk>/reactivate/", LawyerClientReactivateView.as_view(), name="lawyer-client-reactivate"),
    path("clients/stats/", LawyerClientStatsView.as_view(), name="lawyer-clients-stats"),

    # Matter management (scoped to lawyer)
    path("matters/", LawyerMatterListCreateView.as_view(), name="lawyer-matters-list-create"),
    path("matters/<int:pk>/", LawyerMatterDetailView.as_view(), name="lawyer-matter-detail"),
    path("matters/stats/", LawyerMatterStatsView.as_view(), name="lawyer-matters-stats"),

    # Overall dashboard stats
    path("stats/", LawyerOverviewStatsView.as_view(), name="lawyer-overview-stats"),
]
