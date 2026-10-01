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


class IsLawyerOrIndividualFirmAdmin(BasePermission):
    """
    Allows access strictly to Lawyers and INDIVIDUAL Firm Administrators.
    Super Admins, Multi Firm Admins, and other roles are forbidden.
    """

    message = "Only Lawyers and INDIVIDUAL Firm Administrators are allowed to manage clerks."

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if user.role == UserRole.LAWYER:
            return True
        if user.role == UserRole.FIRM_ADMIN:
            from apps.firm.views import _get_or_create_user_firm

            firm = _get_or_create_user_firm(user)
            return bool(firm and firm.is_individual)
        return False

