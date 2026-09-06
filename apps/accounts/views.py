"""
Views for the accounts app.

All views follow the same response envelope used across the project:

    Success:  { "data": {...} }
    Error:    { "errors": {...} }   (DRF default validation format)
"""

import logging

from django.contrib.auth import update_session_auth_hash
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView as BaseTokenRefreshView

from .emails import send_password_reset_email
from .models import PasswordResetToken, User
from .serializers import (
    ChangePasswordSerializer,
    ForgotPasswordSerializer,
    LoginSerializer,
    LogoutSerializer,
    ProfilePhotoSerializer,
    ResetPasswordSerializer,
    UserProfileMiniSerializer,
    UserProfileSerializer,
)
from .tokens import generate_password_reset_token, verify_password_reset_token

logger = logging.getLogger(__name__)


class LoginThrottle(AnonRateThrottle):
    scope = "login"


class ForgotPasswordThrottle(AnonRateThrottle):
    scope = "forgot_password"


# ─── Login ────────────────────────────────────────────────────────────────────


@extend_schema(tags=["Authentication"])
class LoginView(APIView):
    """
    Authenticate a user with email + password.

    Returns JWT access/refresh tokens and the user's profile.
    """

    permission_classes = [AllowAny]
    throttle_classes = [LoginThrottle]

    @extend_schema(
        summary="Login",
        description=(
            "Authenticate with email and password. "
            "Returns access token, refresh token, and user profile."
        ),
        request=LoginSerializer,
        responses={
            200: OpenApiResponse(description="Authentication successful"),
            400: OpenApiResponse(description="Invalid credentials or inactive account"),
        },
        examples=[
            OpenApiExample(
                "Login Request",
                value={"email": "user@example.com", "password": "s3cur3P@ss"},
                request_only=True,
            )
        ],
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data

        user: User = validated["user"]
        user_data = UserProfileMiniSerializer(user, context={"request": request}).data

        return Response(
            {
                "access": validated["access"],
                "refresh": validated["refresh"],
                "user": user_data,
            },
            status=status.HTTP_200_OK,
        )


# ─── Token Refresh ────────────────────────────────────────────────────────────


@extend_schema(tags=["Authentication"])
class TokenRefreshView(BaseTokenRefreshView):
    """Obtain a new access token by supplying a valid refresh token."""


# ─── Logout ───────────────────────────────────────────────────────────────────


@extend_schema(tags=["Authentication"])
class LogoutView(APIView):
    """
    Logout the authenticated user by blacklisting their refresh token.

    After this call the submitted refresh token is permanently invalidated.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Logout",
        description="Blacklist the provided refresh token, ending the user's session.",
        request=LogoutSerializer,
        responses={
            200: OpenApiResponse(description="Successfully logged out"),
            400: OpenApiResponse(description="Invalid or missing refresh token"),
        },
    )
    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        raw_refresh = serializer.validated_data["refresh"]
        try:
            token = RefreshToken(raw_refresh)
            token.blacklist()
        except TokenError as exc:
            return Response(
                {"errors": {"refresh": [str(exc)]}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({"message": "Successfully logged out."}, status=status.HTTP_200_OK)


# ─── Me (current user profile) ────────────────────────────────────────────────


@extend_schema(tags=["User"])
class MeView(APIView):
    """Retrieve the profile of the currently authenticated user."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get current user",
        description="Return the profile of the authenticated user.",
        responses={200: UserProfileSerializer},
    )
    def get(self, request):
        serializer = UserProfileSerializer(request.user, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)


# ─── Change Password ──────────────────────────────────────────────────────────


@extend_schema(tags=["User"])
class ChangePasswordView(APIView):
    """
    Change the authenticated user's password.

    On success, all outstanding refresh tokens for this user are revoked.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Change password",
        description=(
            "Verify the current password, validate and set the new one, "
            "then revoke all outstanding refresh tokens for security."
        ),
        request=ChangePasswordSerializer,
        responses={
            200: OpenApiResponse(description="Password changed successfully"),
            400: OpenApiResponse(description="Validation error"),
        },
    )
    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        user: User = request.user
        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])

        # Keep the current Django session valid (relevant if session auth is in use)
        update_session_auth_hash(request, user)

        # Revoke all outstanding refresh tokens for this user
        _revoke_all_refresh_tokens(user)

        return Response(
            {"message": "Password changed successfully. Please log in again."},
            status=status.HTTP_200_OK,
        )


# ─── Forgot Password ──────────────────────────────────────────────────────────


@extend_schema(tags=["User"])
class ForgotPasswordView(APIView):
    """
    Initiate the password-reset flow by sending a reset link to the user's email.

    Always returns the same response regardless of whether the email exists
    in the system (prevents user enumeration).
    """

    permission_classes = [AllowAny]
    throttle_classes = [ForgotPasswordThrottle]

    GENERIC_RESPONSE = {
        "message": "If an account exists for this email, a password reset link has been sent."
    }

    @extend_schema(
        summary="Forgot password",
        description=(
            "Request a password-reset email. The response is always the same "
            "generic message to avoid revealing whether the email is registered."
        ),
        request=ForgotPasswordSerializer,
        responses={200: OpenApiResponse(description="Generic success response")},
    )
    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"].lower().strip()

        try:
            user = User.objects.get(email=email, is_active=True)
        except User.DoesNotExist:
            # Always return the same response — do NOT reveal email existence
            return Response(self.GENERIC_RESPONSE, status=status.HTTP_200_OK)

        raw_token, _ = generate_password_reset_token(user)
        try:
            send_password_reset_email(user, raw_token)
        except Exception:
            # Log server-side but don't surface to the client
            logger.exception("Failed to send password reset email to %s", email)

        return Response(self.GENERIC_RESPONSE, status=status.HTTP_200_OK)


# ─── Reset Password ───────────────────────────────────────────────────────────


@extend_schema(tags=["User"])
class ResetPasswordView(APIView):
    """
    Complete the password-reset flow by supplying the token and the new password.

    On success, all outstanding refresh tokens for this user are revoked.
    """

    permission_classes = [AllowAny]

    @extend_schema(
        summary="Reset password",
        description=(
            "Submit the reset token (received via email) and a new password. "
            "The token is single-use and expires after 1 hour."
        ),
        request=ResetPasswordSerializer,
        responses={
            200: OpenApiResponse(description="Password reset successfully"),
            400: OpenApiResponse(description="Invalid, expired, or already-used token"),
        },
    )
    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        raw_token: str = serializer.validated_data["token"]
        new_password: str = serializer.validated_data["new_password"]

        token_instance = verify_password_reset_token(raw_token)
        if token_instance is None:
            return Response(
                {"errors": {"token": ["Invalid, expired, or already-used reset token."]}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user: User = token_instance.user

        # Mark token as used (single-use)
        token_instance.used = True
        token_instance.save(update_fields=["used"])

        user.set_password(new_password)
        user.save(update_fields=["password"])

        # Revoke all outstanding refresh tokens for security
        _revoke_all_refresh_tokens(user)

        return Response(
            {"message": "Password reset successfully. Please log in with your new password."},
            status=status.HTTP_200_OK,
        )


# ─── Profile Photo ────────────────────────────────────────────────────────────


@extend_schema(tags=["User"])
class ProfilePhotoView(APIView):
    """Upload or replace the authenticated user's profile photo."""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser]

    @extend_schema(
        summary="Upload profile photo",
        description=(
            "Upload a new profile photo (JPEG, PNG, GIF, or WEBP; max 5 MB). "
            "Replaces any existing photo."
        ),
        request=ProfilePhotoSerializer,
        responses={
            200: UserProfileSerializer,
            400: OpenApiResponse(description="Validation error (invalid type or size)"),
        },
    )
    def patch(self, request):
        user: User = request.user
        old_photo = user.profile_photo

        serializer = ProfilePhotoSerializer(
            user,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)

        # Delete old photo from storage before saving the new one
        if old_photo:
            old_photo.delete(save=False)

        serializer.save()

        profile = UserProfileSerializer(user, context={"request": request})
        return Response(profile.data, status=status.HTTP_200_OK)


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _revoke_all_refresh_tokens(user: User) -> None:
    """
    Blacklist every outstanding refresh token belonging to *user*.

    This is called after a password change/reset to invalidate all
    existing sessions.
    """
    from rest_framework_simplejwt.token_blacklist.models import (
        BlacklistedToken,
        OutstandingToken,
    )

    tokens = OutstandingToken.objects.filter(user=user)
    for token in tokens:
        BlacklistedToken.objects.get_or_create(token=token)
