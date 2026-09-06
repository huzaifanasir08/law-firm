"""
Role-based permission classes for the Law Firm platform.

Usage example::

    class MyView(APIView):
        permission_classes = [IsAuthenticated, IsFirmAdmin]
"""

from rest_framework.permissions import BasePermission

from .models import UserRole


class IsRole(BasePermission):
    """
    Base class for role-based permission checks.

    Subclasses must set ``allowed_roles`` to a list of ``UserRole`` values.
    """

    allowed_roles: list[str] = []

    def has_permission(self, request, view) -> bool:
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in self.allowed_roles
        )


class IsSuperAdmin(IsRole):
    """Allow only users with the SUPER_ADMIN role."""

    message = "Only Super Admins are allowed to perform this action."
    allowed_roles = [UserRole.SUPER_ADMIN]


class IsFirmAdmin(IsRole):
    """Allow only users with the FIRM_ADMIN role."""

    message = "Only Firm Admins are allowed to perform this action."
    allowed_roles = [UserRole.FIRM_ADMIN]


class IsLawyer(IsRole):
    """Allow only users with the LAWYER role."""

    message = "Only Lawyers are allowed to perform this action."
    allowed_roles = [UserRole.LAWYER]


class IsClerk(IsRole):
    """Allow only users with the CLERK role."""

    message = "Only Clerks are allowed to perform this action."
    allowed_roles = [UserRole.CLERK]


class IsAdminRole(IsRole):
    """Allow SUPER_ADMIN or FIRM_ADMIN roles."""

    message = "Only Admin users are allowed to perform this action."
    allowed_roles = [UserRole.SUPER_ADMIN, UserRole.FIRM_ADMIN]


class IsLawyerOrAbove(IsRole):
    """Allow SUPER_ADMIN, FIRM_ADMIN, or LAWYER roles."""

    message = "Only Lawyers or above are allowed to perform this action."
    allowed_roles = [UserRole.SUPER_ADMIN, UserRole.FIRM_ADMIN, UserRole.LAWYER]
