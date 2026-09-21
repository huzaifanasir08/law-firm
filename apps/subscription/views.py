from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import filters, generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import IsSuperAdmin
from apps.administration.pagination import StandardResultsSetPagination
from .filters import PlanFilter, SubscriptionFilter, TransactionFilter
from .models import Plan, Subscription, Transaction
from .serializers import (
    AdminCreateSubscriptionSerializer,
    PlanSerializer,
    SubscriptionSerializer,
    SubscriptionUpdateSerializer,
    TransactionSerializer,
)


# ─── Plans ───────────────────────────────────────────────────────────────────

@extend_schema_view(
    get=extend_schema(
        tags=["Plans"],
        summary="List public subscription plans",
        description="Public endpoint to list active plans available for firms.",
        responses={200: PlanSerializer(many=True)},
        auth=[],
    ),
)
class PublicPlanListView(generics.ListAPIView):
    """Public listing of available subscription tiers."""

    permission_classes = [AllowAny]
    queryset = Plan.objects.filter(is_active=True, is_public=True)
    serializer_class = PlanSerializer


@extend_schema_view(
    get=extend_schema(
        tags=["Plans"],
        summary="List all subscription plans (Admin)",
        description="Super Admin endpoint to list all plans with filtering and search.",
        responses={200: PlanSerializer(many=True)},
    ),
    post=extend_schema(
        tags=["Plans"],
        summary="Create subscription plan (Admin)",
        description="Super Admin endpoint to create a new subscription plan tier.",
        request=PlanSerializer,
        responses={201: PlanSerializer, 400: OpenApiResponse(description="Validation error")},
    ),
)
class AdminPlanListCreateView(generics.ListCreateAPIView):
    """Super Admin endpoint to list or create subscription plans."""

    permission_classes = [IsAuthenticated, IsSuperAdmin]
    queryset = Plan.objects.all()
    serializer_class = PlanSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = PlanFilter
    search_fields = ["name", "description"]
    ordering_fields = ["price", "name", "created_at"]
    ordering = ["price"]


@extend_schema_view(
    get=extend_schema(
        tags=["Plans"],
        summary="Retrieve plan details (Admin)",
        responses={200: PlanSerializer, 404: OpenApiResponse(description="Plan not found")},
    ),
    put=extend_schema(
        tags=["Plans"],
        summary="Update plan (Admin)",
        request=PlanSerializer,
        responses={200: PlanSerializer, 400: OpenApiResponse(description="Validation error")},
    ),
    patch=extend_schema(
        tags=["Plans"],
        summary="Partial update plan (Admin)",
        request=PlanSerializer,
        responses={200: PlanSerializer, 400: OpenApiResponse(description="Validation error")},
    ),
    delete=extend_schema(
        tags=["Plans"],
        summary="Delete plan (Admin)",
        responses={204: OpenApiResponse(description="Plan deleted"), 404: OpenApiResponse(description="Plan not found")},
    ),
)
class AdminPlanDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Super Admin endpoint to retrieve, update, or remove a plan tier."""

    permission_classes = [IsAuthenticated, IsSuperAdmin]
    queryset = Plan.objects.all()
    serializer_class = PlanSerializer


# ─── Transactions ─────────────────────────────────────────────────────────────

@extend_schema_view(
    get=extend_schema(
        tags=["Transactions"],
        summary="List transactions (Admin)",
        description="Super Admin endpoint to list payment transactions with pagination, filters, and search.",
        parameters=[
            OpenApiParameter("page", int, description="Page number"),
            OpenApiParameter("page_size", int, description="Number of results per page (max 100)"),
            OpenApiParameter("search", str, description="Search across transaction ID, firm name, bank accounts"),
        ],
        responses={200: TransactionSerializer(many=True)},
    ),
)
class AdminTransactionListView(generics.ListAPIView):
    """Super Admin endpoint to inspect payment transactions."""

    permission_classes = [IsAuthenticated, IsSuperAdmin]
    pagination_class = StandardResultsSetPagination
    queryset = Transaction.objects.select_related("firm", "firm_admin").all()
    serializer_class = TransactionSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = TransactionFilter
    search_fields = [
        "transaction_id",
        "firm__name",
        "firm_admin__email",
        "firm_admin__name",
        "sender_bank_account",
        "receiver_bank_account",
    ]
    ordering_fields = ["date", "amount", "created_at"]
    ordering = ["-date"]


@extend_schema_view(
    get=extend_schema(
        tags=["Transactions"],
        summary="Retrieve transaction details (Admin)",
        responses={200: TransactionSerializer, 404: OpenApiResponse(description="Transaction not found")},
    ),
)
class AdminTransactionDetailView(generics.RetrieveAPIView):
    """Super Admin endpoint to retrieve full details of a specific payment transaction."""

    permission_classes = [IsAuthenticated, IsSuperAdmin]
    queryset = Transaction.objects.select_related("firm", "firm_admin").all()
    serializer_class = TransactionSerializer


# ─── Subscriptions ────────────────────────────────────────────────────────────

@extend_schema_view(
    get=extend_schema(
        tags=["Subscriptions"],
        summary="List subscriptions (Admin)",
        description="Super Admin endpoint to list firm subscriptions with pagination, filtering, and search.",
        parameters=[
            OpenApiParameter("page", int, description="Page number"),
            OpenApiParameter("page_size", int, description="Number of results per page (max 100)"),
            OpenApiParameter("search", str, description="Search across firm name, admin email, plan name"),
        ],
        responses={200: SubscriptionSerializer(many=True)},
    ),
    post=extend_schema(
        tags=["Subscriptions"],
        summary="Create subscription and payment transaction (Admin)",
        description=(
            "Composite endpoint for Super Admins. Allows submitting a single form containing "
            "firm admin user, plan, payment method, bank accounts, and trial options. "
            "Automatically calculates trial/end dates, pricing, statuses, and links the transaction atomically."
        ),
        request=AdminCreateSubscriptionSerializer,
        responses={
            201: SubscriptionSerializer,
            400: OpenApiResponse(description="Validation error"),
        },
    ),
)
class AdminSubscriptionListCreateView(generics.ListCreateAPIView):
    """
    Super Admin endpoint to list all firm subscriptions or composite-create
    a new subscription with linked payment transaction and auto-calculated dates.
    """

    permission_classes = [IsAuthenticated, IsSuperAdmin]
    pagination_class = StandardResultsSetPagination
    queryset = Subscription.objects.select_related("plan", "transaction", "firm", "firm_admin").all()
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = SubscriptionFilter
    search_fields = [
        "firm__name",
        "firm_admin__email",
        "firm_admin__name",
        "plan__name",
        "transaction__transaction_id",
    ]
    ordering_fields = ["created_at", "started_at", "ends_at", "status"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return AdminCreateSubscriptionSerializer
        return SubscriptionSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        subscription = serializer.save()
        output_serializer = SubscriptionSerializer(subscription, context={"request": request})
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)


@extend_schema_view(
    get=extend_schema(
        tags=["Subscriptions"],
        summary="Retrieve subscription details (Admin)",
        responses={200: SubscriptionSerializer, 404: OpenApiResponse(description="Subscription not found")},
    ),
    put=extend_schema(
        tags=["Subscriptions"],
        summary="Update subscription (Admin)",
        request=SubscriptionUpdateSerializer,
        responses={200: SubscriptionSerializer, 400: OpenApiResponse(description="Validation error")},
    ),
    patch=extend_schema(
        tags=["Subscriptions"],
        summary="Partial update subscription (Admin)",
        request=SubscriptionUpdateSerializer,
        responses={200: SubscriptionSerializer, 400: OpenApiResponse(description="Validation error")},
    ),
    delete=extend_schema(
        tags=["Subscriptions"],
        summary="Delete subscription (Admin)",
        responses={204: OpenApiResponse(description="Subscription deleted"), 404: OpenApiResponse(description="Subscription not found")},
    ),
)
class AdminSubscriptionDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Super Admin endpoint to view, edit, or remove a firm subscription."""

    permission_classes = [IsAuthenticated, IsSuperAdmin]
    queryset = Subscription.objects.select_related("plan", "transaction", "firm", "firm_admin").all()

    def get_serializer_class(self):
        if self.request.method in ["PUT", "PATCH"]:
            return SubscriptionUpdateSerializer
        return SubscriptionSerializer
