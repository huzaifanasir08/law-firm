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
from apps.leads.views import AdminLeadDetailView, AdminLeadListView
from apps.subscription.views import (
    AdminPlanDetailView,
    AdminPlanListCreateView,
    AdminSubscriptionDetailView,
    AdminSubscriptionListCreateView,
    AdminTransactionDetailView,
    AdminTransactionListView,
)

app_name = "administration"

urlpatterns = [
    path("users/", AdminUserListCreateView.as_view(), name="user-list-create"),
    path("users/<int:pk>/", AdminUserDetailView.as_view(), name="user-detail"),
    path("firms/", AdminFirmListCreateView.as_view(), name="firm-list-create"),
    path("firms/<int:pk>/", AdminFirmDetailView.as_view(), name="firm-detail"),
    path("leads/", AdminLeadListView.as_view(), name="lead-list"),
    path("leads/<int:pk>/", AdminLeadDetailView.as_view(), name="lead-detail"),
    # Plans management
    path("plans/", AdminPlanListCreateView.as_view(), name="plan-list-create"),
    path("plans/<int:pk>/", AdminPlanDetailView.as_view(), name="plan-detail"),
    # Transactions management
    path("transactions/", AdminTransactionListView.as_view(), name="transaction-list"),
    path("transactions/<int:pk>/", AdminTransactionDetailView.as_view(), name="transaction-detail"),
    # Subscriptions management & composite onboarding
    path("subscriptions/", AdminSubscriptionListCreateView.as_view(), name="subscription-list-create"),
    path("subscriptions/<int:pk>/", AdminSubscriptionDetailView.as_view(), name="subscription-detail"),
    path("stats/", AdminStatsView.as_view(), name="stats"),
]
