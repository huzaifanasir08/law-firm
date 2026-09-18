"""
URL configuration for the administration app.

Mounted under ``/api/admin/`` by the project's root urls.py.
"""

from django.urls import path

from .views import (
    AdminFirmDetailView,
    AdminFirmListCreateView,
    AdminStatsView,
    AdminUserDetailView,
    AdminUserListCreateView,
)

app_name = "administration"

urlpatterns = [
    path("users/", AdminUserListCreateView.as_view(), name="user-list-create"),
    path("users/<int:pk>/", AdminUserDetailView.as_view(), name="user-detail"),
    path("firms/", AdminFirmListCreateView.as_view(), name="firm-list-create"),
    path("firms/<int:pk>/", AdminFirmDetailView.as_view(), name="firm-detail"),
    path("stats/", AdminStatsView.as_view(), name="stats"),
]
