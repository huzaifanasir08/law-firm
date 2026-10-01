"""
Permissions for the clerk app.
"""

from rest_framework.permissions import BasePermission

from apps.accounts.models import UserRole


class IsClerkUser(BasePermission):
    """
    Allows access only to authenticated users with the CLERK role.
    """

    message = "Only Clerks are allowed to access this resource."

    def has_permission(self, request, view) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == UserRole.CLERK
        )
