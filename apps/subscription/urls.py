from django.urls import path

from .views import (
    AdminPlanDetailView,
    AdminPlanListCreateView,
    AdminSubscriptionDetailView,
    AdminSubscriptionListCreateView,
    AdminTransactionDetailView,
    AdminTransactionListView,
    PublicPlanListView,
)

app_name = "subscription"

urlpatterns = [
    # Public plan list
    path("plans/", PublicPlanListView.as_view(), name="public-plan-list"),
    # Direct admin routes under subscription app (if accessed directly via /api/subscription/admin/...)
    path("admin/plans/", AdminPlanListCreateView.as_view(), name="admin-plan-list-create"),
    path("admin/plans/<int:pk>/", AdminPlanDetailView.as_view(), name="admin-plan-detail"),
    path("admin/transactions/", AdminTransactionListView.as_view(), name="admin-transaction-list"),
    path("admin/transactions/<int:pk>/", AdminTransactionDetailView.as_view(), name="admin-transaction-detail"),
    path("admin/subscriptions/", AdminSubscriptionListCreateView.as_view(), name="admin-subscription-list-create"),
    path("admin/subscriptions/<int:pk>/", AdminSubscriptionDetailView.as_view(), name="admin-subscription-detail"),
]
