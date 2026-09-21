"""
URL configuration for project project.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),

    # Accounts / Auth
    path("api/accounts/", include("apps.accounts.urls")),

    # Admin Management & Stats
    path("api/admin/", include("apps.administration.urls")),

    # Firm Management & Stats
    path("api/firm/", include("apps.firm.urls")),

    # Lawyer Management, Clients, Matters & Stats
    path("api/lawyer/", include("apps.lawyer.urls")),

    # Matters Management & Stats
    path("api/matters/", include("apps.matters.urls")),

    # Leads (Public submission)
    path("api/leads/", include("apps.leads.urls")),

    # Subscription
    path("api/subscription/", include("apps.subscription.urls")),

    # OpenAPI schema & docs
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
