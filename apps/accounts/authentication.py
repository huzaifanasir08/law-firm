"""
Custom JWT authentication backend.

Extends simplejwt's default ``JWTAuthentication`` to also check whether
an *access* token has been explicitly blacklisted.  By default, simplejwt
only blacklists refresh tokens — this class adds a belt-and-suspenders
check so that access tokens invalidated via logout or password-change are
rejected even before they naturally expire.
"""

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken


class BlacklistAwareJWTAuthentication(JWTAuthentication):
    """
    JWTAuthentication subclass that validates access tokens against the
    simplejwt blacklist.

    If the token's ``jti`` claim matches a blacklisted outstanding token,
    authentication is rejected.
    """

    def get_validated_token(self, raw_token):
        validated = super().get_validated_token(raw_token)

        jti = validated.get("jti")
        if jti:
            try:
                outstanding = OutstandingToken.objects.get(jti=jti)
                if BlacklistedToken.objects.filter(token=outstanding).exists():
                    raise TokenError("Token has been blacklisted.")
            except OutstandingToken.DoesNotExist:
                # Outstanding token record doesn't exist — this is acceptable
                # for short-lived access tokens; let simplejwt's signature
                # and expiry checks handle validity.
                pass

        return validated
