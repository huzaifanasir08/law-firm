"""
URL configuration for the matters app.
"""

from django.urls import path

from .views import (
    LawyerMatterDetailView,
    LawyerMatterListCreateView,
    LawyerMatterStatsView,
)

urlpatterns = [
    path("", LawyerMatterListCreateView.as_view(), name="matter-list-create"),
    path("<int:pk>/", LawyerMatterDetailView.as_view(), name="matter-detail"),
    path("stats/", LawyerMatterStatsView.as_view(), name="matter-stats"),
]
