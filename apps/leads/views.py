from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import filters, generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated

from apps.accounts.permissions import IsSuperAdmin
from apps.administration.pagination import StandardResultsSetPagination
from .filters import LeadFilter
from .models import (
    Lead,
    LeadContactWay,
    LeadInterest,
    LeadInterestedFirm,
    LeadPreferredTime,
    LeadStatus,
)
from .serializers import (
    AdminLeadSerializer,
    AdminLeadUpdateSerializer,
    PublicLeadCreateSerializer,
)


@extend_schema_view(
    post=extend_schema(
        tags=["Leads"],
        summary="Submit a new lead inquiry/registration",
        description=(
            "Public endpoint to register a new lead. "
            "Guarantees that a lead with the same email cannot be submitted twice. "
            "Newly submitted leads are automatically assigned a 'pending' status."
        ),
        request=PublicLeadCreateSerializer,
        responses={
            201: PublicLeadCreateSerializer,
            400: OpenApiResponse(description="Validation error (e.g., duplicate email or missing fields)"),
        },
        auth=[],
    ),
)
class PublicLeadCreateView(generics.CreateAPIView):
    """Public endpoint for submitting new leads."""

    permission_classes = [AllowAny]
    serializer_class = PublicLeadCreateSerializer
    queryset = Lead.objects.all()


@extend_schema_view(
    get=extend_schema(
        tags=["Admin - Leads"],
        summary="List all leads",
        description=(
            "Retrieve leads with pagination, search, and filtering. "
            "Requires Super Admin privileges."
        ),
        parameters=[
            OpenApiParameter("page", int, description="Page number"),
            OpenApiParameter("page_size", int, description="Number of results per page (max 100)"),
            OpenApiParameter("search", str, description="Search across name, email, phone, and address"),
            OpenApiParameter("status", str, enum=LeadStatus.values, description="Filter by status"),
            OpenApiParameter("interest", str, enum=LeadInterest.values, description="Filter by interest"),
            OpenApiParameter("interested_firm", str, enum=LeadInterestedFirm.values, description="Filter by interested firm type"),
            OpenApiParameter("preferred_time", str, enum=LeadPreferredTime.values, description="Filter by preferred contact time"),
            OpenApiParameter("preferred_contact_way", str, enum=LeadContactWay.values, description="Filter by preferred contact channel"),
            OpenApiParameter("created_after", str, description="Filter leads created after datetime (ISO 8601)"),
            OpenApiParameter("created_before", str, description="Filter leads created before datetime (ISO 8601)"),
        ],
        responses={200: AdminLeadSerializer(many=True)},
    ),
)
class AdminLeadListView(generics.ListAPIView):
    """Super Admin endpoint to list and filter all prospective leads."""

    permission_classes = [IsAuthenticated, IsSuperAdmin]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = LeadFilter
    search_fields = ["name", "email", "phone", "address"]
    ordering_fields = [
        "created_at",
        "name",
        "email",
        "status",
        "interest",
        "interested_firm",
    ]
    ordering = ["-created_at"]
    queryset = Lead.objects.all()
    serializer_class = AdminLeadSerializer


@extend_schema_view(
    get=extend_schema(
        tags=["Admin - Leads"],
        summary="Retrieve lead details",
        description="Retrieve complete details for a specific lead. Requires Super Admin privileges.",
        responses={
            200: AdminLeadSerializer,
            404: OpenApiResponse(description="Lead not found"),
        },
    ),
    put=extend_schema(
        tags=["Admin - Leads"],
        summary="Update lead",
        description="Update details, status, or notes for a lead. Requires Super Admin privileges.",
        request=AdminLeadUpdateSerializer,
        responses={
            200: AdminLeadSerializer,
            400: OpenApiResponse(description="Validation error"),
            404: OpenApiResponse(description="Lead not found"),
        },
    ),
    patch=extend_schema(
        tags=["Admin - Leads"],
        summary="Partial update lead",
        description="Partially update status, internal notes, or contact info for a lead. Requires Super Admin privileges.",
        request=AdminLeadUpdateSerializer,
        responses={
            200: AdminLeadSerializer,
            400: OpenApiResponse(description="Validation error"),
            404: OpenApiResponse(description="Lead not found"),
        },
    ),
    delete=extend_schema(
        tags=["Admin - Leads"],
        summary="Delete lead",
        description="Delete a lead record. Requires Super Admin privileges.",
        responses={
            204: OpenApiResponse(description="Lead deleted successfully"),
            404: OpenApiResponse(description="Lead not found"),
        },
    ),
)
class AdminLeadDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Super Admin endpoint to view, edit, or remove a lead."""

    permission_classes = [IsAuthenticated, IsSuperAdmin]
    queryset = Lead.objects.all()

    def get_serializer_class(self):
        if self.request.method in ["PUT", "PATCH"]:
            return AdminLeadUpdateSerializer
        return AdminLeadSerializer
