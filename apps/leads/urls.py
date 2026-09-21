from django.urls import path

from .views import (
    AdminLeadDetailView,
    AdminLeadListView,
    PublicLeadCreateView,
)

app_name = "leads"

urlpatterns = [
    path("", PublicLeadCreateView.as_view(), name="lead-create"),
    # Also provide direct lead routes in case accessed under /api/leads/
    path("admin/", AdminLeadListView.as_view(), name="admin-leads-list"),
    path("admin/<int:pk>/", AdminLeadDetailView.as_view(), name="admin-leads-detail"),
]
