"""
Permissions for the firm app.
"""

from rest_framework.permissions import BasePermission

from apps.accounts.models import UserRole



def get_user_firm(user):
    """Helper to retrieve or initialize a firm for a firm administrator."""
    if getattr(user, "firm", None):
        return user.firm
    from apps.firm.models import Firm, FirmType
    firm, _ = Firm.objects.get_or_create(
        name=f"{user.name}'s Firm",
        defaults={"email": user.email, "phone": user.phone, "type": FirmType.MULTI},
    )
    user.firm = firm
    user.save(update_fields=["firm"])
    return firm


class IsFirmAdminOrSuperAdmin(BasePermission):
    """
    Allows access only to Firm Admins and Super Admins.
    """

    message = "Only Firm Admins or Super Admins are allowed to manage firm resources."

    def has_permission(self, request, view) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in [UserRole.FIRM_ADMIN, UserRole.SUPER_ADMIN]
        )


class CanManageFirmLawyers(BasePermission):
    """
    Permission class enforcing that:
    - Adding lawyers (POST) is allowed for MULTI Firm Admins and Super Admins.
    - Adding lawyers (POST) is FORBIDDEN (403) for INDIVIDUAL Firm Admins.
    - Managing lawyers (PUT, PATCH, DELETE, reactivate) is FORBIDDEN (403) for INDIVIDUAL Firm Admins.
    """

    message = "Firms with individual type cannot add or manage lawyers."

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not (user and user.is_authenticated):
            return False

        if user.role == UserRole.SUPER_ADMIN:
            return True

        if user.role == UserRole.FIRM_ADMIN:
            firm = get_user_firm(user)
            if firm.is_individual:
                if request.method in ["POST", "PUT", "PATCH", "DELETE"]:
                    return False
            return True

        return False

