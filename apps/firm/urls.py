"""
URL configuration for the firm app.
"""

from django.urls import path

from .views import (
    FirmClerkDetailView,
    FirmClerkListCreateView,
    FirmClerkReactivateView,
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
    path("clerks/", FirmClerkListCreateView.as_view(), name="firm-clerks-list-create"),
    path("clerks/<int:pk>/", FirmClerkDetailView.as_view(), name="firm-clerk-detail"),
    path("clerks/<int:pk>/reactivate/", FirmClerkReactivateView.as_view(), name="firm-clerk-reactivate"),
    path("stats/", FirmStatsView.as_view(), name="firm-stats"),
]
