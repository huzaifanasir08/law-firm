"""
Permissions for the lawyer app.
"""

from rest_framework.permissions import BasePermission

from apps.accounts.models import UserRole


class IsLawyerUser(BasePermission):
    """
    Allows access to Lawyers, Firm Admins, and Super Admins.
    """

    message = "Only Lawyers or Admins are allowed to access this resource."

    def has_permission(self, request, view) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in [UserRole.LAWYER, UserRole.FIRM_ADMIN, UserRole.SUPER_ADMIN]
        )
