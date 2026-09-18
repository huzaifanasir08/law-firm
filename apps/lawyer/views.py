"""
Views for the lawyer app.
"""

import logging
from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import filters, generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import UserRole
from apps.administration.pagination import StandardResultsSetPagination
from apps.firm.models import FirmType
from apps.firm.views import _get_or_create_user_firm
from .filters import LawyerClientFilter
from .models import Client
from .permissions import IsLawyerUser
from .serializers import (
    ClientSerializer,
    ClientStatsSerializer,
    ClientUpdateSerializer,
)

logger = logging.getLogger(__name__)


@extend_schema_view(
    get=extend_schema(
        tags=["Lawyer - Clients"],
        summary="List lawyer clients",
        description="List all clients managed by the authenticated lawyer with search, filtering, and pagination.",
        parameters=[
            OpenApiParameter("page", int, description="Page number"),
            OpenApiParameter("page_size", int, description="Number of results per page (max 100)"),
            OpenApiParameter("search", str, description="Search across client name, email, and phone"),
            OpenApiParameter("is_active", bool, description="Filter by active status"),
            OpenApiParameter("created_after", str, description="Filter clients created after datetime (ISO 8601)"),
            OpenApiParameter("created_before", str, description="Filter clients created before datetime (ISO 8601)"),
        ],
        responses={200: ClientSerializer(many=True)},
    ),
    post=extend_schema(
        tags=["Lawyer - Clients"],
        summary="Create client",
        description=(
            "Add a new client record managed by the authenticated lawyer or individual firm admin. "
            "Clients are system data records with the 'CLIENT' role; no login credentials are generated or sent."
        ),
        request=ClientSerializer,
        responses={
            201: ClientSerializer,
            400: OpenApiResponse(description="Validation error"),
            403: OpenApiResponse(description="Permission denied"),
        },
    ),
)
class LawyerClientListCreateView(generics.ListCreateAPIView):
    """List and create client records for the authenticated lawyer or individual firm admin."""

    permission_classes = [IsAuthenticated, IsLawyerUser]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = LawyerClientFilter
    search_fields = ["name", "email", "phone"]
    ordering_fields = ["created_at", "name", "email", "is_active"]
    ordering = ["-created_at"]
    queryset = Client.objects.none()

    def get_queryset(self):
        user = self.request.user
        if getattr(self, "swagger_fake_view", False) or not user.is_authenticated:
            return Client.objects.none()
        if user.is_superuser:
            return Client.objects.all().order_by("-created_at")
        if user.role == UserRole.FIRM_ADMIN:
            firm = _get_or_create_user_firm(user)
            if firm.is_multi:
                return Client.objects.filter(firm=firm).order_by("-created_at")
            else:
                return Client.objects.filter(Q(lawyer=user) | Q(firm=firm)).order_by("-created_at")
        return Client.objects.filter(lawyer=user).order_by("-created_at")

    def get_serializer_class(self):
        return ClientSerializer

    def create(self, request, *args, **kwargs):
        user = request.user
        if user.role == UserRole.FIRM_ADMIN:
            firm = _get_or_create_user_firm(user)
            if firm.is_multi:
                return Response(
                    {"detail": "Firms with multi type can only list clients, not add or manage them."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        return super().create(request, *args, **kwargs)


@extend_schema_view(
    get=extend_schema(
        tags=["Lawyer - Clients"],
        summary="Retrieve client details",
        description="Get detailed information for a specific client managed by the lawyer or firm.",
        responses={200: ClientSerializer, 404: OpenApiResponse(description="Client not found")},
    ),
    put=extend_schema(
        tags=["Lawyer - Clients"],
        summary="Update client details",
        description="Update a client's details.",
        request=ClientUpdateSerializer,
        responses={200: ClientSerializer, 400: OpenApiResponse(description="Validation error")},
    ),
    patch=extend_schema(
        tags=["Lawyer - Clients"],
        summary="Partially update client details",
        description="Partially update a client's details.",
        request=ClientUpdateSerializer,
        responses={200: ClientSerializer, 400: OpenApiResponse(description="Validation error")},
    ),
    delete=extend_schema(
        tags=["Lawyer - Clients"],
        summary="Soft-delete client",
        description="Mark a client as inactive (soft delete only). Data is preserved.",
        responses={200: OpenApiResponse(description="Client marked as inactive successfully")},
    ),
)
class LawyerClientDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or soft-delete a client."""

    permission_classes = [IsAuthenticated, IsLawyerUser]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Client.objects.all()
        if user.role == UserRole.FIRM_ADMIN:
            firm = _get_or_create_user_firm(user)
            if firm.is_multi:
                return Client.objects.filter(firm=firm)
            else:
                return Client.objects.filter(Q(lawyer=user) | Q(firm=firm))
        return Client.objects.filter(lawyer=user)

    def get_serializer_class(self):
        if self.request.method in ["PUT", "PATCH"]:
            return ClientUpdateSerializer
        return ClientSerializer

    def update(self, request, *args, **kwargs):
        user = request.user
        if user.role == UserRole.FIRM_ADMIN:
            firm = _get_or_create_user_firm(user)
            if firm.is_multi:
                return Response(
                    {"detail": "Firms with multi type can only list clients, not add or manage them."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial, context={"request": request})
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        output_serializer = ClientSerializer(instance, context={"request": request})
        return Response(output_serializer.data, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        user = request.user
        if user.role == UserRole.FIRM_ADMIN:
            firm = _get_or_create_user_firm(user)
            if firm.is_multi:
                return Response(
                    {"detail": "Firms with multi type can only list clients, not add or manage them."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        instance = self.get_object()
        instance.is_active = False
        instance.save(update_fields=["is_active", "updated_at"])
        return Response(
            {"message": "Client marked as inactive successfully.", "id": instance.id, "is_active": False},
            status=status.HTTP_200_OK,
        )


@extend_schema(
    tags=["Lawyer - Clients"],
    summary="Reactivate an inactive client",
    description="Reactivate a previously soft-deleted client.",
    request=None,
    responses={
        200: OpenApiResponse(description="Client reactivated successfully"),
        404: OpenApiResponse(description="Client not found"),
    },
)
class LawyerClientReactivateView(APIView):
    """Reactivate a soft-deleted client."""

    permission_classes = [IsAuthenticated, IsLawyerUser]

    def post(self, request, pk: int):
        user = request.user
        if user.role == UserRole.FIRM_ADMIN:
            firm = _get_or_create_user_firm(user)
            if firm.is_multi:
                return Response(
                    {"detail": "Firms with multi type can only list clients, not add or manage them."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            queryset = Client.objects.filter(Q(lawyer=user) | Q(firm=firm))
        elif user.is_superuser:
            queryset = Client.objects.all()
        else:
            queryset = Client.objects.filter(lawyer=user)

        try:
            client = queryset.get(id=pk)
        except Client.DoesNotExist:
            return Response({"detail": "Client not found."}, status=status.HTTP_404_NOT_FOUND)

        client.is_active = True
        client.save(update_fields=["is_active", "updated_at"])
        return Response(
            {"message": "Client reactivated successfully.", "id": client.id, "is_active": True},
            status=status.HTTP_200_OK,
        )


@extend_schema(
    tags=["Lawyer - Statistics"],
    summary="Get lawyer client statistics",
    description="Retrieve client metrics for the authenticated lawyer including total clients, active clients, inactive clients, and total matters across all clients.",
    responses={200: ClientStatsSerializer},
)
class LawyerClientStatsView(APIView):
    """Retrieve client metrics for the authenticated lawyer."""

    permission_classes = [IsAuthenticated, IsLawyerUser]

    def get(self, request):
        user = request.user
        from apps.matters.models import Matter

        if user.is_superuser:
            clients = Client.objects.all()
            total_matters = Matter.objects.filter(client__in=clients).count()
        elif user.role == UserRole.FIRM_ADMIN:
            firm = _get_or_create_user_firm(user)
            if firm.is_multi:
                clients = Client.objects.filter(firm=firm)
                total_matters = Matter.objects.filter(firm=firm).count()
            else:
                clients = Client.objects.filter(Q(lawyer=user) | Q(firm=firm))
                total_matters = Matter.objects.filter(Q(lawyer=user) | Q(firm=firm)).count()
        else:
            clients = Client.objects.filter(lawyer=user)
            total_matters = Matter.objects.filter(lawyer=user, client__in=clients).count()

        total_clients = clients.count()
        active_clients = clients.filter(is_active=True).count()
        inactive_clients = clients.filter(is_active=False).count()

        data = {
            "total_clients": total_clients,
            "active_clients": active_clients,
            "inactive_clients": inactive_clients,
            "total_matters": total_matters,
        }

        serializer = ClientStatsSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)


@extend_schema(
    tags=["Lawyer - Statistics"],
    summary="Get lawyer overall dashboard statistics",
    description="Retrieve combined statistics for clients and matters handled by the authenticated lawyer.",
    responses={200: OpenApiResponse(description="Combined overview stats for clients and matters")},
)
class LawyerOverviewStatsView(APIView):
    """Retrieve comprehensive overview stats for lawyer dashboard."""

    permission_classes = [IsAuthenticated, IsLawyerUser]

    def get(self, request):
        user = request.user
        from datetime import timedelta
        from django.utils import timezone
        from apps.matters.models import Matter, MatterStatus

        if user.is_superuser:
            clients = Client.objects.all()
            matters = Matter.objects.all()
        elif user.role == UserRole.FIRM_ADMIN:
            firm = _get_or_create_user_firm(user)
            if firm.is_multi:
                clients = Client.objects.filter(firm=firm)
                matters = Matter.objects.filter(firm=firm)
            else:
                clients = Client.objects.filter(Q(lawyer=user) | Q(firm=firm))
                matters = Matter.objects.filter(Q(lawyer=user) | Q(firm=firm))
        else:
            clients = Client.objects.filter(lawyer=user)
            matters = Matter.objects.filter(lawyer=user)

        today = timezone.now().date()
        next_week = today + timedelta(days=7)

        data = {
            "clients": {
                "total": clients.count(),
                "active": clients.filter(is_active=True).count(),
                "inactive": clients.filter(is_active=False).count(),
            },
            "matters": {
                "total": matters.count(),
                "open": matters.filter(status__in=[MatterStatus.OPEN, MatterStatus.IN_PROGRESS, MatterStatus.PENDING]).count(),
                "closed": matters.filter(status=MatterStatus.CLOSED).count(),
                "due": matters.filter(due_date__lte=today).exclude(status=MatterStatus.CLOSED).count(),
                "upcoming": matters.filter(due_date__gt=today, due_date__lte=next_week).exclude(status=MatterStatus.CLOSED).count(),
            },
        }
        return Response(data, status=status.HTTP_200_OK)

