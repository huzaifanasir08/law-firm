"""
Views for the matters app.
"""

from datetime import timedelta
from django.db.models import Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import filters, generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import UserRole
from apps.accounts.permissions import IsLawyerOrAbove
from apps.administration.pagination import StandardResultsSetPagination
from apps.firm.views import _get_or_create_user_firm
from .filters import MatterFilter
from .models import Matter, MatterPriority, MatterStatus
from .serializers import MatterSerializer, MatterStatsSerializer


@extend_schema_view(
    get=extend_schema(
        tags=["Lawyer - Matters"],
        summary="List matters",
        description="List all legal matters scoped to the authenticated lawyer or firm with filtering, search, and pagination.",
        parameters=[
            OpenApiParameter("page", int, description="Page number"),
            OpenApiParameter("page_size", int, description="Number of results per page (max 100)"),
            OpenApiParameter("search", str, description="Search across title, case number, and description"),
            OpenApiParameter("status", str, enum=MatterStatus.values, description="Filter by matter status"),
            OpenApiParameter("priority", str, enum=MatterPriority.values, description="Filter by priority"),
            OpenApiParameter("client", int, description="Filter by client ID"),
            OpenApiParameter("is_due", bool, description="Filter matters that are due or overdue"),
            OpenApiParameter("due_before", str, description="Filter matters due before date (YYYY-MM-DD)"),
            OpenApiParameter("due_after", str, description="Filter matters due after date (YYYY-MM-DD)"),
        ],
        responses={200: MatterSerializer(many=True)},
    ),
    post=extend_schema(
        tags=["Lawyer - Matters"],
        summary="Create matter",
        description="Create a new legal matter scoped to the authenticated lawyer or individual firm admin and linked to one of their clients.",
        request=MatterSerializer,
        responses={
            201: MatterSerializer,
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Permission denied"),
        },
    ),
)
class LawyerMatterListCreateView(generics.ListCreateAPIView):
    """List and create matters scoped to the requesting lawyer or individual firm admin."""

    permission_classes = [IsAuthenticated, IsLawyerOrAbove]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = MatterFilter
    search_fields = ["title", "case_number", "description"]
    ordering_fields = ["created_at", "title", "case_number", "status", "priority", "due_date"]
    ordering = ["-created_at"]
    queryset = Matter.objects.none()

    def get_queryset(self):
        user = self.request.user
        if getattr(self, "swagger_fake_view", False) or not user.is_authenticated:
            return Matter.objects.none()
        if user.is_superuser:
            return Matter.objects.all().order_by("-created_at")
        if user.role == UserRole.FIRM_ADMIN:
            firm = _get_or_create_user_firm(user)
            if firm.is_multi:
                return Matter.objects.filter(firm=firm).order_by("-created_at")
            else:
                return Matter.objects.filter(Q(lawyer=user) | Q(firm=firm)).order_by("-created_at")
        return Matter.objects.filter(lawyer=user).order_by("-created_at")

    def get_serializer_class(self):
        return MatterSerializer

    def create(self, request, *args, **kwargs):
        user = request.user
        if user.role == UserRole.FIRM_ADMIN:
            firm = _get_or_create_user_firm(user)
            if firm.is_multi:
                return Response(
                    {"detail": "Firms with multi type can only list matters, not add or manage them."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        return super().create(request, *args, **kwargs)


@extend_schema_view(
    get=extend_schema(
        tags=["Lawyer - Matters"],
        summary="Retrieve matter details",
        description="Get detailed information for a specific legal matter scoped to the lawyer or firm.",
        responses={200: MatterSerializer, 404: OpenApiResponse(description="Matter not found")},
    ),
    put=extend_schema(
        tags=["Lawyer - Matters"],
        summary="Update matter",
        description="Update a legal matter.",
        request=MatterSerializer,
        responses={
            200: MatterSerializer,
            400: OpenApiResponse(description="Validation error"),
            404: OpenApiResponse(description="Matter not found"),
        },
    ),
    patch=extend_schema(
        tags=["Lawyer - Matters"],
        summary="Partially update matter",
        description="Partially update a legal matter.",
        request=MatterSerializer,
        responses={
            200: MatterSerializer,
            400: OpenApiResponse(description="Validation error"),
            404: OpenApiResponse(description="Matter not found"),
        },
    ),
    delete=extend_schema(
        tags=["Lawyer - Matters"],
        summary="Delete matter",
        description="Permanently delete a legal matter scoped to the lawyer.",
        responses={204: OpenApiResponse(description="Matter deleted successfully"), 404: OpenApiResponse(description="Matter not found")},
    ),
)
class LawyerMatterDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a legal matter."""

    permission_classes = [IsAuthenticated, IsLawyerOrAbove]
    serializer_class = MatterSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Matter.objects.all()
        if user.role == UserRole.FIRM_ADMIN:
            firm = _get_or_create_user_firm(user)
            if firm.is_multi:
                return Matter.objects.filter(firm=firm)
            else:
                return Matter.objects.filter(Q(lawyer=user) | Q(firm=firm))
        return Matter.objects.filter(lawyer=user)

    def update(self, request, *args, **kwargs):
        user = request.user
        if user.role == UserRole.FIRM_ADMIN:
            firm = _get_or_create_user_firm(user)
            if firm.is_multi:
                return Response(
                    {"detail": "Firms with multi type can only list matters, not add or manage them."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        user = request.user
        if user.role == UserRole.FIRM_ADMIN:
            firm = _get_or_create_user_firm(user)
            if firm.is_multi:
                return Response(
                    {"detail": "Firms with multi type can only list matters, not add or manage them."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        return super().destroy(request, *args, **kwargs)


@extend_schema(
    tags=["Lawyer - Statistics"],
    summary="Get lawyer matter statistics",
    description="Retrieve statistics for legal matters handled by the authenticated lawyer or firm (total, open, closed, due, and upcoming).",
    responses={200: MatterStatsSerializer},
)
class LawyerMatterStatsView(APIView):
    """Retrieve matter metrics scoped to the lawyer or firm."""

    permission_classes = [IsAuthenticated, IsLawyerOrAbove]

    def get(self, request):
        user = request.user
        if user.is_superuser:
            queryset = Matter.objects.all()
        elif user.role == UserRole.FIRM_ADMIN:
            firm = _get_or_create_user_firm(user)
            if firm.is_multi:
                queryset = Matter.objects.filter(firm=firm)
            else:
                queryset = Matter.objects.filter(Q(lawyer=user) | Q(firm=firm))
        else:
            queryset = Matter.objects.filter(lawyer=user)

        today = timezone.now().date()
        next_week = today + timedelta(days=7)

        total_matters = queryset.count()
        open_matters = queryset.filter(
            status__in=[MatterStatus.OPEN, MatterStatus.IN_PROGRESS, MatterStatus.PENDING]
        ).count()
        closed_matters = queryset.filter(status=MatterStatus.CLOSED).count()
        due_matters = (
            queryset.filter(due_date__lte=today)
            .exclude(status=MatterStatus.CLOSED)
            .count()
        )
        upcoming_matters = (
            queryset.filter(due_date__gt=today, due_date__lte=next_week)
            .exclude(status=MatterStatus.CLOSED)
            .count()
        )

        data = {
            "total_matters": total_matters,
            "open_matters": open_matters,
            "closed_matters": closed_matters,
            "due_matters": due_matters,
            "upcoming_matters": upcoming_matters,
        }

        serializer = MatterStatsSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)

