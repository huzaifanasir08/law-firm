"""
Project-level pytest fixtures shared across all test modules.
"""

import pytest
from django.core.cache import cache
from django.contrib.auth import get_user_model

from apps.accounts.models import UserRole

User = get_user_model()


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear Django's cache before every test to reset DRF throttle counters."""
    cache.clear()


@pytest.fixture
def api_client():
    from rest_framework.test import APIClient
    return APIClient()


@pytest.fixture
def make_user(db):
    """Factory fixture: call make_user(**kwargs) to create a User."""
    def _make_user(
        email="test@example.com",
        password="Secur3P@ssword!",
        name="Test User",
        role=UserRole.CLERK,
        is_active=True,
        **kwargs,
    ):
        user = User.objects.create_user(
            email=email,
            password=password,
            name=name,
            role=role,
            is_active=is_active,
            **kwargs,
        )
        user._plain_password = password  # Store for assertions
        return user

    return _make_user


@pytest.fixture
def user(make_user):
    return make_user()


@pytest.fixture
def super_admin(make_user):
    return make_user(
        email="superadmin@example.com",
        role=UserRole.SUPER_ADMIN,
        is_staff=True,
        is_superuser=True,
    )


@pytest.fixture
def firm_admin(make_user):
    return make_user(email="firmadmin@example.com", role=UserRole.FIRM_ADMIN)


@pytest.fixture
def lawyer(make_user):
    return make_user(email="lawyer@example.com", role=UserRole.LAWYER)


@pytest.fixture
def auth_client(api_client, user):
    """API client pre-authenticated as the default test user."""
    from rest_framework_simplejwt.tokens import RefreshToken
    refresh = RefreshToken.for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    api_client._user = user
    return api_client
