"""
URL configuration for the clerk app.
"""

from django.urls import path

from .views import (
    ClerkProfileView,
    ClerkTaskDetailView,
    ClerkTaskListView,
    ClerkTaskUpdateStatusView,
)

urlpatterns = [
    path("tasks/", ClerkTaskListView.as_view(), name="clerk-tasks-list"),
    path("tasks/<int:pk>/", ClerkTaskDetailView.as_view(), name="clerk-task-detail"),
    path("tasks/<int:pk>/status/", ClerkTaskUpdateStatusView.as_view(), name="clerk-task-status-update"),
    path("profile/", ClerkProfileView.as_view(), name="clerk-profile"),
]
