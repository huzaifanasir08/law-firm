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


def validate_user_subscription(user) -> None:
    """
    Validate that the user's firm has a valid active subscription or valid trial.
    Raises rest_framework.exceptions.PermissionDenied (HTTP 403) if invalid.
    Super Admins are exempt from firm subscription checks.
    Non-super-admin users without an assigned firm are blocked.
    """
    from django.utils.translation import gettext_lazy as _
    from rest_framework.exceptions import PermissionDenied

    if user.is_super_admin or user.is_superuser or user.role == UserRole.SUPER_ADMIN:
        return

    if not user.firm:
        raise PermissionDenied(
            str(_("Your account is not associated with any firm. Please contact support or your administrator."))
        )

    is_valid, message = user.firm.get_subscription_status()
    if not is_valid:
        raise PermissionDenied(message)


class HasValidFirmSubscription(BasePermission):
    """
    Permission class ensuring the authenticated user belongs to an active firm
    with an active subscription or valid trial. Super Admins are exempt.
    """

    message = "Your firm does not have an active subscription or valid trial."

    def has_permission(self, request, view) -> bool:
        from rest_framework.exceptions import PermissionDenied

        if not (request.user and request.user.is_authenticated):
            return False
        try:
            validate_user_subscription(request.user)
            return True
        except PermissionDenied as exc:
            self.message = str(exc.detail) if hasattr(exc, "detail") else str(exc)
            return False
