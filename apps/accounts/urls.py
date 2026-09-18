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
    OTPSendView,
    OTPResendView,
    OTPVerifyView,
    ProfilePhotoView,
    ResetPasswordView,
    TokenRefreshView,
    TwoFAConfirmChangeView,
    TwoFARequestChangeView,
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

    # ── OTP & Two-Factor Authentication ──────────────────────────────────────
    path("otp/send/", OTPSendView.as_view(), name="otp-send"),
    path("otp/resend/", OTPResendView.as_view(), name="otp-resend"),
    path("otp/verify/", OTPVerifyView.as_view(), name="otp-verify"),
    path("2fa/request-change/", TwoFARequestChangeView.as_view(), name="2fa-request-change"),
    path("2fa/confirm-change/", TwoFAConfirmChangeView.as_view(), name="2fa-confirm-change"),
]
