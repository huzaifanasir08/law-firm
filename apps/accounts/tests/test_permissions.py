"""
Tests for role values and permission classes.
"""

import pytest
from rest_framework.permissions import IsAuthenticated
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView

from apps.accounts.models import UserRole
from apps.accounts.permissions import (
    IsAdminRole,
    IsClerk,
    IsFirmAdmin,
    IsLawyer,
    IsLawyerOrAbove,
    IsSuperAdmin,
)


@pytest.mark.django_db
class TestUserRoles:
    def test_user_role_choices(self):
        choices = {c[0] for c in UserRole.choices}
        assert "SUPER_ADMIN" in choices
        assert "FIRM_ADMIN" in choices
        assert "LAWYER" in choices
        assert "CLERK" in choices

    def test_default_role_is_clerk(self, make_user):
        user = make_user(email="default@example.com")
        assert user.role == UserRole.CLERK

    def test_super_admin_property(self, make_user):
        user = make_user(email="sa@example.com", role=UserRole.SUPER_ADMIN)
        assert user.is_super_admin is True
        assert user.is_firm_admin is False

    def test_firm_admin_property(self, make_user):
        user = make_user(email="fa@example.com", role=UserRole.FIRM_ADMIN)
        assert user.is_firm_admin is True
        assert user.is_super_admin is False

    def test_lawyer_property(self, make_user):
        user = make_user(email="lw@example.com", role=UserRole.LAWYER)
        assert user.is_lawyer is True

    def test_clerk_property(self, make_user):
        user = make_user(email="cl@example.com", role=UserRole.CLERK)
        assert user.is_clerk is True


class _MockRequest:
    """Minimal request mock for permission tests."""
    def __init__(self, user):
        self.user = user


@pytest.mark.django_db
class TestPermissionClasses:
    def _check(self, permission_class, user) -> bool:
        request = _MockRequest(user)
        perm = permission_class()
        return perm.has_permission(request, None)

    def test_is_super_admin_allows_super_admin(self, make_user):
        user = make_user(email="p1@example.com", role=UserRole.SUPER_ADMIN)
        assert self._check(IsSuperAdmin, user) is True

    def test_is_super_admin_rejects_firm_admin(self, make_user):
        user = make_user(email="p2@example.com", role=UserRole.FIRM_ADMIN)
        assert self._check(IsSuperAdmin, user) is False

    def test_is_firm_admin_allows_firm_admin(self, make_user):
        user = make_user(email="p3@example.com", role=UserRole.FIRM_ADMIN)
        assert self._check(IsFirmAdmin, user) is True

    def test_is_firm_admin_rejects_lawyer(self, make_user):
        user = make_user(email="p4@example.com", role=UserRole.LAWYER)
        assert self._check(IsFirmAdmin, user) is False

    def test_is_lawyer_allows_lawyer(self, make_user):
        user = make_user(email="p5@example.com", role=UserRole.LAWYER)
        assert self._check(IsLawyer, user) is True

    def test_is_clerk_allows_clerk(self, make_user):
        user = make_user(email="p6@example.com", role=UserRole.CLERK)
        assert self._check(IsClerk, user) is True

    def test_is_admin_role_allows_super_admin(self, make_user):
        user = make_user(email="p7@example.com", role=UserRole.SUPER_ADMIN)
        assert self._check(IsAdminRole, user) is True

    def test_is_admin_role_allows_firm_admin(self, make_user):
        user = make_user(email="p8@example.com", role=UserRole.FIRM_ADMIN)
        assert self._check(IsAdminRole, user) is True

    def test_is_admin_role_rejects_lawyer(self, make_user):
        user = make_user(email="p9@example.com", role=UserRole.LAWYER)
        assert self._check(IsAdminRole, user) is False

    def test_is_lawyer_or_above_allows_super_admin(self, make_user):
        user = make_user(email="p10@example.com", role=UserRole.SUPER_ADMIN)
        assert self._check(IsLawyerOrAbove, user) is True

    def test_is_lawyer_or_above_allows_lawyer(self, make_user):
        user = make_user(email="p11@example.com", role=UserRole.LAWYER)
        assert self._check(IsLawyerOrAbove, user) is True

    def test_is_lawyer_or_above_rejects_clerk(self, make_user):
        user = make_user(email="p12@example.com", role=UserRole.CLERK)
        assert self._check(IsLawyerOrAbove, user) is False
