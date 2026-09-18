"""
URL configuration for the firm app.
"""

from django.urls import path

from .views import (
    FirmLawyerDetailView,
    FirmLawyerListCreateView,
    FirmLawyerReactivateView,
    FirmProfileView,
    FirmStatsView,
)

urlpatterns = [
    path("profile/", FirmProfileView.as_view(), name="firm-profile"),
    path("lawyers/", FirmLawyerListCreateView.as_view(), name="firm-lawyers-list-create"),
    path("lawyers/<int:pk>/", FirmLawyerDetailView.as_view(), name="firm-lawyer-detail"),
    path("lawyers/<int:pk>/reactivate/", FirmLawyerReactivateView.as_view(), name="firm-lawyer-reactivate"),
    path("stats/", FirmStatsView.as_view(), name="firm-stats"),
]
