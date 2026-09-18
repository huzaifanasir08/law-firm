"""
Views for the administration app.
"""

import logging

from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import filters, generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User, UserRole
from apps.accounts.permissions import IsAdminRole, IsSuperAdmin
from apps.accounts.views import _revoke_all_refresh_tokens
from apps.firm.models import Firm, FirmType
from apps.firm.serializers import FirmSerializer
from .filters import UserAdminFilter
from .pagination import StandardResultsSetPagination
from .serializers import (
    AdminCreateUserSerializer,
    AdminStatsSerializer,
    AdminUserSerializer,
    AdminUserUpdateSerializer,
)

logger = logging.getLogger(__name__)


@extend_schema_view(
    get=extend_schema(
        tags=["Admin - Users"],
        summary="List all users",
        description=(
            "List users with pagination, search, and filtering. "
            "Excludes the currently authenticated user from the result list."
        ),
        parameters=[
            OpenApiParameter("page", int, description="Page number"),
            OpenApiParameter("page_size", int, description="Number of results per page (max 100)"),
            OpenApiParameter("search", str, description="Search across name, email, and phone"),
            OpenApiParameter(
                "role",
                str,
                enum=UserRole.values,
                description="Filter by user role",
            ),
            OpenApiParameter("is_active", bool, description="Filter by active status"),
            OpenApiParameter("created_after", str, description="Filter users created after datetime (ISO 8601)"),
            OpenApiParameter("created_before", str, description="Filter users created before datetime (ISO 8601)"),
        ],
        responses={200: AdminUserSerializer(many=True)},
    ),
    post=extend_schema(
        tags=["Admin - Users"],
        summary="Create new user",
        description=(
            "Create a new user. Only Super Admins can create users (Super Admins only). "
            "Creating Law Firm Admins from this endpoint is not allowed. "
            "A secure password is generated automatically and sent via email."
        ),
        request=AdminCreateUserSerializer,
        responses={
            201: AdminUserSerializer,
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Permission denied"),
        },
    ),
)
class AdminUserListCreateView(generics.ListCreateAPIView):
    """List all users (excluding self) or create a new super admin user."""

    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = UserAdminFilter
    search_fields = ["name", "email", "phone"]
    ordering_fields = ["created_at", "name", "email", "role", "is_active", "last_login"]
    ordering = ["-created_at"]

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated(), IsSuperAdmin()]
        return [IsAuthenticated(), IsAdminRole()]

    def get_queryset(self):
        user = self.request.user
        # Exclude the requesting user from the list
        return User.objects.exclude(id=user.id).order_by("-created_at")

    def get_serializer_class(self):
        if self.request.method == "POST":
            return AdminCreateUserSerializer
        return AdminUserSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        output_serializer = AdminUserSerializer(user, context={"request": request})
        headers = self.get_success_headers(output_serializer.data)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED, headers=headers)


@extend_schema_view(
    get=extend_schema(
        tags=["Admin - Users"],
        summary="Retrieve user details",
        description="Get detailed profile information for a specific user.",
        responses={
            200: AdminUserSerializer,
            404: OpenApiResponse(description="User not found"),
        },
    ),
    put=extend_schema(
        tags=["Admin - Users"],
        summary="Update user",
        description="Update user attributes such as name, phone, address, role, and active status.",
        request=AdminUserUpdateSerializer,
        responses={
            200: AdminUserSerializer,
            400: OpenApiResponse(description="Validation error"),
            404: OpenApiResponse(description="User not found"),
        },
    ),
    patch=extend_schema(
        tags=["Admin - Users"],
        summary="Partial update user",
        description="Partially update user attributes.",
        request=AdminUserUpdateSerializer,
        responses={
            200: AdminUserSerializer,
            400: OpenApiResponse(description="Validation error"),
            404: OpenApiResponse(description="User not found"),
        },
    ),
    delete=extend_schema(
        tags=["Admin - Users"],
        summary="Delete user",
        description="Permanently delete a user account and invalidate active sessions.",
        responses={
            204: OpenApiResponse(description="User deleted successfully"),
            400: OpenApiResponse(description="Cannot delete self or last Super Admin"),
            404: OpenApiResponse(description="User not found"),
        },
    ),
)
class AdminUserDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a specific user account."""

    permission_classes = [IsAuthenticated, IsAdminRole]
    queryset = User.objects.all()

    def get_serializer_class(self):
        if self.request.method in ["PUT", "PATCH"]:
            return AdminUserUpdateSerializer
        return AdminUserSerializer

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()

        # Firm Admins cannot edit Super Admin accounts
        if request.user.role == UserRole.FIRM_ADMIN and instance.role == UserRole.SUPER_ADMIN:
            return Response(
                {"detail": "Firm Admins cannot modify Super Admin accounts."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = self.get_serializer(instance, data=request.data, partial=partial, context={"request": request})
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        output_serializer = AdminUserSerializer(instance, context={"request": request})
        return Response(output_serializer.data, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()

        # Prevent deleting oneself
        if instance.id == request.user.id:
            return Response(
                {"detail": "You cannot delete your own account through this endpoint."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Firm Admins cannot delete Super Admin accounts
        if request.user.role == UserRole.FIRM_ADMIN and instance.role == UserRole.SUPER_ADMIN:
            return Response(
                {"detail": "Firm Admins cannot delete Super Admin accounts."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Prevent deleting the last Super Admin
        if instance.role == UserRole.SUPER_ADMIN:
            other_super_admins = User.objects.filter(role=UserRole.SUPER_ADMIN, is_active=True).exclude(id=instance.id).count()
            if other_super_admins == 0:
                return Response(
                    {"detail": "Cannot delete the last active Super Admin account."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Revoke all outstanding tokens before deleting
        _revoke_all_refresh_tokens(instance)
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    tags=["Admin - Statistics"],
    summary="Get platform statistics",
    description=(
        "Retrieve platform usage and user metrics including total users, "
        "active users, registrations this and last month, total firm admins, and total lawyers."
    ),
    responses={200: AdminStatsSerializer},
)
class AdminStatsView(APIView):
    """Retrieve platform statistics for administrators."""

    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        now = timezone.now()

        total_users = User.objects.count()
        total_active_users = User.objects.filter(is_active=True).count()

        # Current month
        users_this_month = User.objects.filter(
            created_at__year=now.year,
            created_at__month=now.month,
        ).count()

        # Last month
        if now.month == 1:
            last_month_year = now.year - 1
            last_month = 12
        else:
            last_month_year = now.year
            last_month = now.month - 1

        users_last_month = User.objects.filter(
            created_at__year=last_month_year,
            created_at__month=last_month,
        ).count()

        total_firm_admins = User.objects.filter(role=UserRole.FIRM_ADMIN).count()
        total_lawyers = User.objects.filter(role=UserRole.LAWYER).count()

        data = {
            "total_users": total_users,
            "total_active_users": total_active_users,
            "users_this_month": users_this_month,
            "users_last_month": users_last_month,
            "total_firm_admins": total_firm_admins,
            "total_lawyers": total_lawyers,
        }

        serializer = AdminStatsSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)


@extend_schema_view(
    get=extend_schema(
        tags=["Admin - Firms"],
        summary="List all firms",
        description="List all law firms registered on the platform with search, type filter, and pagination.",
        parameters=[
            OpenApiParameter("page", int, description="Page number"),
            OpenApiParameter("page_size", int, description="Number of results per page (max 100)"),
            OpenApiParameter("search", str, description="Search across firm name, email, and phone"),
            OpenApiParameter("type", str, enum=["INDIVIDUAL", "MULTI"], description="Filter by firm type"),
            OpenApiParameter("is_active", bool, description="Filter by active status"),
        ],
        responses={200: FirmSerializer(many=True)},
    ),
    post=extend_schema(
        tags=["Admin - Firms"],
        summary="Create a new firm",
        description="Create a new firm entity specifying its type (INDIVIDUAL or MULTI) and profile details.",
        request=FirmSerializer,
        responses={
            201: FirmSerializer,
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Permission denied"),
        },
    ),
)
class AdminFirmListCreateView(generics.ListCreateAPIView):
    """List all firms or create a new firm with type specification."""

    permission_classes = [IsAuthenticated, IsAdminRole]
    serializer_class = FirmSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "email", "phone", "registration_number"]
    filterset_fields = ["type", "is_active"]
    ordering_fields = ["created_at", "name", "type", "is_active"]
    ordering = ["-created_at"]
    queryset = Firm.objects.all()


@extend_schema_view(
    get=extend_schema(
        tags=["Admin - Firms"],
        summary="Retrieve firm details",
        description="Get detailed profile information for a specific firm.",
        responses={200: FirmSerializer, 404: OpenApiResponse(description="Firm not found")},
    ),
    put=extend_schema(
        tags=["Admin - Firms"],
        summary="Update firm details",
        description="Update firm attributes including type (INDIVIDUAL or MULTI).",
        request=FirmSerializer,
        responses={
            200: FirmSerializer,
            400: OpenApiResponse(description="Validation error"),
            404: OpenApiResponse(description="Firm not found"),
        },
    ),
    patch=extend_schema(
        tags=["Admin - Firms"],
        summary="Partially update firm details",
        description="Partially update firm attributes including type (INDIVIDUAL or MULTI).",
        request=FirmSerializer,
        responses={
            200: FirmSerializer,
            400: OpenApiResponse(description="Validation error"),
            404: OpenApiResponse(description="Firm not found"),
        },
    ),
    delete=extend_schema(
        tags=["Admin - Firms"],
        summary="Delete or deactivate firm",
        description="Permanently delete a firm entity.",
        responses={204: OpenApiResponse(description="Firm deleted successfully"), 404: OpenApiResponse(description="Firm not found")},
    ),
)
class AdminFirmDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update (including type), or delete a firm entity."""

    permission_classes = [IsAuthenticated, IsAdminRole]
    serializer_class = FirmSerializer
    queryset = Firm.objects.all()
