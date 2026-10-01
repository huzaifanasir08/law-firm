"""
Views for the clerk app.
"""

import logging
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import filters, generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.administration.pagination import StandardResultsSetPagination
from apps.lawyer.models import Task
from .filters import ClerkTaskFilter
from .permissions import IsClerkUser
from .serializers import (
    ClerkProfileSerializer,
    ClerkTaskSerializer,
    ClerkTaskStatusUpdateSerializer,
)

logger = logging.getLogger(__name__)


@extend_schema_view(
    get=extend_schema(
        tags=["Clerk - Tasks"],
        summary="List assigned tasks for clerk",
        description="List all tasks assigned to the authenticated clerk with search, filtering, and pagination.",
        parameters=[
            OpenApiParameter("page", int, description="Page number"),
            OpenApiParameter("page_size", int, description="Number of results per page (max 100)"),
            OpenApiParameter("search", str, description="Search across task name and description"),
            OpenApiParameter("status", str, description="Filter by status (PENDING, ASSIGNED, STARTED, COMPLETED, CANCELED)"),
            OpenApiParameter("created_after", str, description="Filter tasks created after datetime (ISO 8601)"),
            OpenApiParameter("created_before", str, description="Filter tasks created before datetime (ISO 8601)"),
        ],
        responses={200: ClerkTaskSerializer(many=True)},
    ),
)
class ClerkTaskListView(generics.ListAPIView):
    """List tasks assigned to the authenticated clerk."""

    permission_classes = [IsAuthenticated, IsClerkUser]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ClerkTaskFilter
    search_fields = ["name", "desc"]
    ordering_fields = ["created_at", "name", "status", "assigned_at", "started_at", "completed_at"]
    ordering = ["-created_at"]
    queryset = Task.objects.none()

    def get_queryset(self):
        user = self.request.user
        if getattr(self, "swagger_fake_view", False) or not user.is_authenticated:
            return Task.objects.none()
        return Task.objects.filter(clerk=user).order_by("-created_at")

    def get_serializer_class(self):
        return ClerkTaskSerializer


@extend_schema_view(
    get=extend_schema(
        tags=["Clerk - Tasks"],
        summary="Retrieve assigned task detail",
        description="Get detailed information for a specific task assigned to the authenticated clerk.",
        responses={200: ClerkTaskSerializer, 404: OpenApiResponse(description="Task not found")},
    ),
    patch=extend_schema(
        tags=["Clerk - Tasks"],
        summary="Update assigned task status",
        description="Update the lifecycle status of a task assigned to the clerk (STARTED, COMPLETED, CANCELED).",
        request=ClerkTaskStatusUpdateSerializer,
        responses={200: ClerkTaskSerializer, 400: OpenApiResponse(description="Validation error")},
    ),
)
class ClerkTaskDetailView(generics.RetrieveUpdateAPIView):
    """Retrieve and update status of a task assigned to the clerk."""

    permission_classes = [IsAuthenticated, IsClerkUser]
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        user = self.request.user
        if getattr(self, "swagger_fake_view", False) or not user.is_authenticated:
            return Task.objects.none()
        return Task.objects.filter(clerk=user)

    def get_serializer_class(self):
        if self.request.method == "PATCH":
            return ClerkTaskStatusUpdateSerializer
        return ClerkTaskSerializer

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", True)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        output_serializer = ClerkTaskSerializer(instance, context={"request": request})
        return Response(output_serializer.data, status=status.HTTP_200_OK)


@extend_schema_view(
    patch=extend_schema(
        tags=["Clerk - Tasks"],
        summary="Update assigned task status (dedicated endpoint)",
        description="Update the lifecycle status of an assigned task to STARTED, COMPLETED, or CANCELED.",
        request=ClerkTaskStatusUpdateSerializer,
        responses={200: ClerkTaskSerializer, 400: OpenApiResponse(description="Validation error")},
    ),
)
class ClerkTaskUpdateStatusView(generics.UpdateAPIView):
    """Dedicated endpoint for updating status of an assigned task."""

    permission_classes = [IsAuthenticated, IsClerkUser]
    serializer_class = ClerkTaskStatusUpdateSerializer
    http_method_names = ["patch", "head", "options"]

    def get_queryset(self):
        user = self.request.user
        if getattr(self, "swagger_fake_view", False) or not user.is_authenticated:
            return Task.objects.none()
        return Task.objects.filter(clerk=user)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        output_serializer = ClerkTaskSerializer(instance, context={"request": request})
        return Response(output_serializer.data, status=status.HTTP_200_OK)


@extend_schema_view(
    get=extend_schema(
        tags=["Clerk - Tasks"],
        summary="Retrieve clerk profile",
        description="Get profile information for the authenticated clerk user.",
        responses={200: ClerkProfileSerializer},
    ),
)
class ClerkProfileView(APIView):
    """Retrieve profile of the currently logged-in clerk."""

    permission_classes = [IsAuthenticated, IsClerkUser]

    def get(self, request):
        serializer = ClerkProfileSerializer(request.user, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)
