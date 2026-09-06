"""
URL configuration for the accounts app.

All URLs are mounted under ``/api/accounts/`` by the project's root urls.py.
"""

from django.urls import path

from .views import (
    ChangePasswordView,
    ForgotPasswordView,
    LoginView,
    LogoutView,
    MeView,
    ProfilePhotoView,
    ResetPasswordView,
    TokenRefreshView,
)

app_name = "accounts"

urlpatterns = [
    # ── Authentication ───────────────────────────────────────────────────────
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("refresh/", TokenRefreshView.as_view(), name="token-refresh"),

    # ── User Profile ─────────────────────────────────────────────────────────
    path("me/", MeView.as_view(), name="me"),
    path("me/photo/", ProfilePhotoView.as_view(), name="me-photo"),

    # ── Password Management ──────────────────────────────────────────────────
    path("change-password/", ChangePasswordView.as_view(), name="change-password"),
    path("forgot-password/", ForgotPasswordView.as_view(), name="forgot-password"),
    path("reset-password/", ResetPasswordView.as_view(), name="reset-password"),
]
