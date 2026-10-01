"""
Views for the firm app.
"""

import logging
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import filters, generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User, UserRole
from apps.accounts.views import _revoke_all_refresh_tokens
from apps.administration.pagination import StandardResultsSetPagination
from .filters import FirmClerkFilter, FirmLawyerFilter
from .models import Firm
from .permissions import (
    CanManageFirmClerks,
    CanManageFirmLawyers,
    IsFirmAdminOrSuperAdmin,
    get_user_firm,
)
from .serializers import (
    FirmClerkSerializer,
    FirmCreateClerkSerializer,
    FirmCreateLawyerSerializer,
    FirmLawyerSerializer,
    FirmSerializer,
    FirmStatsSerializer,
    FirmUpdateClerkSerializer,
    FirmUpdateLawyerSerializer,
)

logger = logging.getLogger(__name__)


def _get_or_create_user_firm(user: User) -> Firm:
    """Helper to retrieve or initialize the user's firm."""
    return get_user_firm(user)



@extend_schema_view(
    get=extend_schema(
        tags=["Firm - Profile"],
        summary="Retrieve firm details",
        description="Get the firm profile belonging to the authenticated administrator.",
        responses={200: FirmSerializer},
    ),
    put=extend_schema(
        tags=["Firm - Profile"],
        summary="Update firm details",
        description="Update firm details such as name, phone, address, and registration number.",
        request=FirmSerializer,
        responses={200: FirmSerializer, 400: OpenApiResponse(description="Validation error")},
    ),
    patch=extend_schema(
        tags=["Firm - Profile"],
        summary="Partially update firm details",
        description="Partially update firm details.",
        request=FirmSerializer,
        responses={200: FirmSerializer, 400: OpenApiResponse(description="Validation error")},
    ),
    post=extend_schema(
        tags=["Firm - Profile"],
        summary="Create or update firm details",
        description="Create or initialize the firm profile for the authenticated administrator with type (INDIVIDUAL or MULTI).",
        request=FirmSerializer,
        responses={
            200: FirmSerializer,
            201: FirmSerializer,
            400: OpenApiResponse(description="Validation error"),
        },
    ),
)
class FirmProfileView(generics.RetrieveUpdateAPIView):
    """View, create, and update firm profile information."""

    permission_classes = [IsAuthenticated, IsFirmAdminOrSuperAdmin]
    serializer_class = FirmSerializer

    def get_object(self) -> Firm:
        return _get_or_create_user_firm(self.request.user)

    def post(self, request, *args, **kwargs):
        user = request.user
        if user.firm:
            serializer = self.get_serializer(user.firm, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        firm = serializer.save()
        user.firm = firm
        user.save(update_fields=["firm"])
        return Response(serializer.data, status=status.HTTP_201_CREATED)


@extend_schema_view(
    get=extend_schema(
        tags=["Firm - Lawyers"],
        summary="List all lawyers in firm",
        description="List all lawyers linked to the administrator's firm with pagination, search, and filtering.",
        parameters=[
            OpenApiParameter("page", int, description="Page number"),
            OpenApiParameter("page_size", int, description="Number of results per page (max 100)"),
            OpenApiParameter("search", str, description="Search across lawyer name, email, and phone"),
            OpenApiParameter("is_active", bool, description="Filter by active status"),
            OpenApiParameter("created_after", str, description="Filter lawyers created after datetime (ISO 8601)"),
            OpenApiParameter("created_before", str, description="Filter lawyers created before datetime (ISO 8601)"),
        ],
        responses={200: FirmLawyerSerializer(many=True)},
    ),
    post=extend_schema(
        tags=["Firm - Lawyers"],
        summary="Add a new lawyer to the firm",
        description=(
            "Add a new lawyer to the firm. A secure password is automatically generated "
            "and sent along with login credentials to the lawyer's email address."
        ),
        request=FirmCreateLawyerSerializer,
        responses={
            201: FirmLawyerSerializer,
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Permission denied"),
        },
    ),
)
class FirmLawyerListCreateView(generics.ListCreateAPIView):
    """List and onboard lawyers for the firm."""

    permission_classes = [IsAuthenticated, IsFirmAdminOrSuperAdmin, CanManageFirmLawyers]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = FirmLawyerFilter
    search_fields = ["name", "email", "phone"]
    ordering_fields = ["created_at", "name", "email", "is_active", "last_login"]
    ordering = ["-created_at"]
    queryset = User.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False) or not self.request.user.is_authenticated:
            return User.objects.none()
        firm = _get_or_create_user_firm(self.request.user)
        if firm.is_individual:
            return User.objects.none()
        return User.objects.filter(firm=firm, role=UserRole.LAWYER).order_by("-created_at")

    def get_serializer_class(self):
        if self.request.method == "POST":
            return FirmCreateLawyerSerializer
        return FirmLawyerSerializer

    def create(self, request, *args, **kwargs):
        firm = _get_or_create_user_firm(request.user)
        if firm.is_individual:
            return Response(
                {"detail": "Firms with individual type cannot add or manage lawyers."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        lawyer = serializer.save()
        output_serializer = FirmLawyerSerializer(lawyer, context={"request": request})
        headers = self.get_success_headers(output_serializer.data)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED, headers=headers)


@extend_schema_view(
    get=extend_schema(
        tags=["Firm - Lawyers"],
        summary="Retrieve lawyer details",
        description="Get detailed profile information for a specific lawyer in the firm.",
        responses={200: FirmLawyerSerializer, 404: OpenApiResponse(description="Lawyer not found")},
    ),
    put=extend_schema(
        tags=["Firm - Lawyers"],
        summary="Update lawyer details",
        description="Update a lawyer's name, phone, address, or active status.",
        request=FirmUpdateLawyerSerializer,
        responses={
            200: FirmLawyerSerializer,
            400: OpenApiResponse(description="Validation error"),
            404: OpenApiResponse(description="Lawyer not found"),
        },
    ),
    patch=extend_schema(
        tags=["Firm - Lawyers"],
        summary="Partially update lawyer details",
        description="Partially update a lawyer's details.",
        request=FirmUpdateLawyerSerializer,
        responses={
            200: FirmLawyerSerializer,
            400: OpenApiResponse(description="Validation error"),
            404: OpenApiResponse(description="Lawyer not found"),
        },
    ),
    delete=extend_schema(
        tags=["Firm - Lawyers"],
        summary="Soft-delete (deactivate) lawyer",
        description="Mark a lawyer as inactive (soft delete only). Invalidates active login tokens without deleting data.",
        responses={
            200: OpenApiResponse(description="Lawyer marked as inactive successfully"),
            404: OpenApiResponse(description="Lawyer not found"),
        },
    ),
)
class FirmLawyerDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or soft-delete (deactivate) a lawyer in the firm."""

    permission_classes = [IsAuthenticated, IsFirmAdminOrSuperAdmin, CanManageFirmLawyers]

    def get_queryset(self):
        firm = _get_or_create_user_firm(self.request.user)
        if firm.is_individual:
            return User.objects.none()
        return User.objects.filter(firm=firm, role=UserRole.LAWYER)

    def get_serializer_class(self):
        if self.request.method in ["PUT", "PATCH"]:
            return FirmUpdateLawyerSerializer
        return FirmLawyerSerializer

    def update(self, request, *args, **kwargs):
        firm = _get_or_create_user_firm(request.user)
        if firm.is_individual:
            return Response(
                {"detail": "Firms with individual type cannot add or manage lawyers."},
                status=status.HTTP_403_FORBIDDEN,
            )
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial, context={"request": request})
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        output_serializer = FirmLawyerSerializer(instance, context={"request": request})
        return Response(output_serializer.data, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        firm = _get_or_create_user_firm(request.user)
        if firm.is_individual:
            return Response(
                {"detail": "Firms with individual type cannot add or manage lawyers."},
                status=status.HTTP_403_FORBIDDEN,
            )
        instance = self.get_object()
        # Soft delete: mark inactive only
        instance.is_active = False
        instance.save(update_fields=["is_active", "updated_at"])

        # Revoke all outstanding JWT refresh tokens
        _revoke_all_refresh_tokens(instance)

        return Response(
            {"message": "Lawyer marked as inactive successfully.", "id": instance.id, "is_active": False},
            status=status.HTTP_200_OK,
        )


@extend_schema(
    tags=["Firm - Lawyers"],
    summary="Reactivate an inactive lawyer",
    description="Reactivate a previously soft-deleted (inactive) lawyer.",
    request=None,
    responses={
        200: OpenApiResponse(description="Lawyer reactivated successfully"),
        404: OpenApiResponse(description="Lawyer not found"),
    },
)
class FirmLawyerReactivateView(APIView):
    """Reactivate a soft-deleted lawyer."""

    permission_classes = [IsAuthenticated, IsFirmAdminOrSuperAdmin, CanManageFirmLawyers]

    def post(self, request, pk: int):
        firm = _get_or_create_user_firm(request.user)
        if firm.is_individual:
            return Response(
                {"detail": "Firms with individual type cannot add or manage lawyers."},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            lawyer = User.objects.get(id=pk, firm=firm, role=UserRole.LAWYER)
        except User.DoesNotExist:
            return Response({"detail": "Lawyer not found."}, status=status.HTTP_404_NOT_FOUND)

        lawyer.is_active = True
        lawyer.save(update_fields=["is_active", "updated_at"])
        return Response(
            {"message": "Lawyer reactivated successfully.", "id": lawyer.id, "is_active": True},
            status=status.HTTP_200_OK,
        )


@extend_schema(
    tags=["Firm - Statistics"],
    summary="Get firm statistics",
    description="Retrieve metrics for the firm including total lawyers, active lawyers, inactive lawyers, and total matters.",
    responses={200: FirmStatsSerializer},
)
class FirmStatsView(APIView):
    """Retrieve statistics for the authenticated user's firm."""

    permission_classes = [IsAuthenticated, IsFirmAdminOrSuperAdmin]

    def get(self, request):
        firm = _get_or_create_user_firm(request.user)
        firm_lawyers = User.objects.filter(firm=firm, role=UserRole.LAWYER)
        total_lawyers = firm_lawyers.count()
        active_lawyers = firm_lawyers.filter(is_active=True).count()
        inactive_lawyers = firm_lawyers.filter(is_active=False).count()

        # Count total matters across all lawyers in this firm
        from apps.matters.models import Matter

        total_matters = Matter.objects.filter(lawyer__in=firm_lawyers).count()

        data = {
            "total_lawyers": total_lawyers,
            "active_lawyers": active_lawyers,
            "inactive_lawyers": inactive_lawyers,
            "total_matters": total_matters,
        }

        serializer = FirmStatsSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)


@extend_schema_view(
    get=extend_schema(
        tags=["Firm - Clerks"],
        summary="List all clerks in firm",
        description="List all clerks linked to the firm with pagination, search, and filtering.",
        parameters=[
            OpenApiParameter("page", int, description="Page number"),
            OpenApiParameter("page_size", int, description="Number of results per page (max 100)"),
            OpenApiParameter("search", str, description="Search across clerk name, email, and phone"),
            OpenApiParameter("is_active", bool, description="Filter by active status"),
            OpenApiParameter("created_after", str, description="Filter clerks created after datetime (ISO 8601)"),
            OpenApiParameter("created_before", str, description="Filter clerks created before datetime (ISO 8601)"),
        ],
        responses={200: FirmClerkSerializer(many=True)},
    ),
    post=extend_schema(
        tags=["Firm - Clerks"],
        summary="Add a new clerk to the firm",
        description=(
            "Add a new clerk to the firm (for individual firm admin or superadmin). "
            "A secure password is automatically generated and sent with login credentials to the clerk's email."
        ),
        request=FirmCreateClerkSerializer,
        responses={
            201: FirmClerkSerializer,
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Permission denied"),
        },
    ),
)
class FirmClerkListCreateView(generics.ListCreateAPIView):
    """List and onboard clerks for the firm (INDIVIDUAL firm admin only)."""

    permission_classes = [IsAuthenticated, CanManageFirmClerks]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = FirmClerkFilter
    search_fields = ["name", "email", "phone"]
    ordering_fields = ["created_at", "name", "email", "is_active", "last_login"]
    ordering = ["-created_at"]
    queryset = User.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False) or not self.request.user.is_authenticated:
            return User.objects.none()
        firm = _get_or_create_user_firm(self.request.user)
        if not firm.is_individual:
            return User.objects.none()
        return User.objects.filter(firm=firm, role=UserRole.CLERK).order_by("-created_at")

    def get_serializer_class(self):
        if self.request.method == "POST":
            return FirmCreateClerkSerializer
        return FirmClerkSerializer

    def create(self, request, *args, **kwargs):
        firm = _get_or_create_user_firm(request.user)
        if request.user.role != UserRole.FIRM_ADMIN or not firm.is_individual:
            return Response(
                {"detail": "Only INDIVIDUAL firm administrators can manage clerks at the firm level."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        clerk = serializer.save()
        output_serializer = FirmClerkSerializer(clerk, context={"request": request})
        headers = self.get_success_headers(output_serializer.data)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED, headers=headers)


@extend_schema_view(
    get=extend_schema(
        tags=["Firm - Clerks"],
        summary="Retrieve clerk details",
        description="Get detailed profile information for a clerk linked to the administrator's firm.",
        responses={200: FirmClerkSerializer, 404: OpenApiResponse(description="Clerk not found")},
    ),
    put=extend_schema(
        tags=["Firm - Clerks"],
        summary="Update clerk details",
        description="Update clerk profile details (name, phone, address, is_active).",
        request=FirmUpdateClerkSerializer,
        responses={200: FirmClerkSerializer, 400: OpenApiResponse(description="Validation error")},
    ),
    patch=extend_schema(
        tags=["Firm - Clerks"],
        summary="Partially update clerk details",
        description="Partially update clerk profile details.",
        request=FirmUpdateClerkSerializer,
        responses={200: FirmClerkSerializer, 400: OpenApiResponse(description="Validation error")},
    ),
    delete=extend_schema(
        tags=["Firm - Clerks"],
        summary="Soft-delete clerk",
        description="Mark a clerk as inactive (soft delete only). Data is preserved.",
        responses={200: OpenApiResponse(description="Clerk marked as inactive successfully")},
    ),
)
class FirmClerkDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or soft-delete a clerk within the firm."""

    permission_classes = [IsAuthenticated, CanManageFirmClerks]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False) or not self.request.user.is_authenticated:
            return User.objects.none()
        firm = _get_or_create_user_firm(self.request.user)
        if not firm.is_individual:
            return User.objects.none()
        return User.objects.filter(firm=firm, role=UserRole.CLERK)

    def get_serializer_class(self):
        if self.request.method in ["PUT", "PATCH"]:
            return FirmUpdateClerkSerializer
        return FirmClerkSerializer

    def update(self, request, *args, **kwargs):
        firm = _get_or_create_user_firm(request.user)
        if request.user.role != UserRole.FIRM_ADMIN or not firm.is_individual:
            return Response(
                {"detail": "Only INDIVIDUAL firm administrators can manage clerks at the firm level."},
                status=status.HTTP_403_FORBIDDEN,
            )
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        output_serializer = FirmClerkSerializer(instance, context={"request": request})
        return Response(output_serializer.data, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        firm = _get_or_create_user_firm(request.user)
        if request.user.role != UserRole.FIRM_ADMIN or not firm.is_individual:
            return Response(
                {"detail": "Only INDIVIDUAL firm administrators can manage clerks at the firm level."},
                status=status.HTTP_403_FORBIDDEN,
            )
        clerk = self.get_object()
        clerk.is_active = False
        clerk.save(update_fields=["is_active", "updated_at"])
        _revoke_all_refresh_tokens(clerk)
        return Response(
            {"message": "Clerk marked as inactive successfully.", "id": clerk.id, "is_active": False},
            status=status.HTTP_200_OK,
        )


@extend_schema(
    tags=["Firm - Clerks"],
    summary="Reactivate an inactive clerk",
    description="Restore an inactive clerk to active status.",
    responses={200: OpenApiResponse(description="Clerk reactivated successfully")},
)
class FirmClerkReactivateView(APIView):
    """Reactivate a previously soft-deleted clerk within the firm."""

    permission_classes = [IsAuthenticated, CanManageFirmClerks]

    def post(self, request, pk: int):
        firm = _get_or_create_user_firm(request.user)
        if request.user.role != UserRole.FIRM_ADMIN or not firm.is_individual:
            return Response(
                {"detail": "Only INDIVIDUAL firm administrators can manage clerks at the firm level."},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            clerk = User.objects.get(pk=pk, firm=firm, role=UserRole.CLERK)
        except User.DoesNotExist:
            return Response({"detail": "Clerk not found."}, status=status.HTTP_404_NOT_FOUND)

        clerk.is_active = True
        clerk.save(update_fields=["is_active", "updated_at"])
        return Response(
            {"message": "Clerk reactivated successfully.", "id": clerk.id, "is_active": True},
            status=status.HTTP_200_OK,
        )

