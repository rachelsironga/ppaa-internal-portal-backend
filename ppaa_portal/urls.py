"""
URL configuration for eapproval_api project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
"""
from django.conf import settings
from django.contrib import admin
from django.http import HttpResponse
from django.urls import path, include, re_path
from rest_framework import permissions
from rest_framework_simplejwt.views import TokenRefreshView

from drf_yasg.views import get_schema_view
from drf_yasg import openapi

from ppaa_auth.utils import MyTokenObtainPairView
from ppaa_portal.public_views import (
    PublicPpaaDashboardView,
    PublicPopupCardEsImageView,
    PublicPortalPrFlyerImageView,
    PublicQuickLinkClickView,
    PublicQuickLinkLogoView,
)
from ppaa_portal.reports_management_views import RmsFinancialPeriodsListView


def api_root_landing(request):
    """Backend has no SPA at `/`; avoid 404 when someone opens http://localhost:8000/."""
    html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>PPAA API</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 40rem; margin: 2rem auto; padding: 0 1rem; line-height: 1.5; }
    h1 { font-size: 1.25rem; }
    ul { padding-left: 1.25rem; }
  </style>
</head>
<body>
  <h1>PPAA Internal Portal — API server</h1>
  <p>This host serves REST APIs only. The web app is usually served by the frontend/nginx container (not port 8000).</p>
  <p>Useful links on this server:</p>
  <ul>
    <li><a href="/swagger/">Swagger UI</a></li>
    <li><a href="/redoc/">ReDoc</a></li>
    <li><a href="/admin/">Django admin</a></li>
  </ul>
</body>
</html>"""
    return HttpResponse(html, content_type="text/html; charset=utf-8")


def favicon_empty(request):
    return HttpResponse(status=204)

schema_view = get_schema_view(
    openapi.Info(
        title="Your API Name",
        default_version="v1",
        description="API documentation",
        terms_of_service="https://yourwebsite.com/terms/",
        contact=openapi.Contact(email="support@yourwebsite.com"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
)


urlpatterns = [
    path("", api_root_landing, name="api-root"),
    path("favicon.ico", favicon_empty, name="favicon"),
    path("admin/", admin.site.urls),
    # Public portal (no auth; must stay under /public/ for TokenAuthMiddleware)
    path(
        "public/ppaa-dashboard/",
        PublicPpaaDashboardView.as_view(),
        name="public-ppaa-dashboard",
    ),
    path(
        "public/quick-links/<str:uid>/logo/",
        PublicQuickLinkLogoView.as_view(),
        name="public-quick-link-logo",
    ),
    path(
        "public/quick-links/<str:uid>/click/",
        PublicQuickLinkClickView.as_view(),
        name="public-quick-link-click",
    ),
    path(
        "public/popup-cards/<str:uid>/es-image/",
        PublicPopupCardEsImageView.as_view(),
        name="public-popup-card-es-image",
    ),
    path(
        "public/pr-flyers/<str:uid>/image/",
        PublicPortalPrFlyerImageView.as_view(),
        name="public-portal-pr-flyer-image",
    ),
    path("user/", include("ppaa_auth.urls")),
    # RMS: financial-periods registered here first so GET /api/reports/financial-periods always resolves
    # (matches before the broader api/reports/ include; avoids 404 if submodule urlpatterns are stale).
    path("api/reports/financial-periods", RmsFinancialPeriodsListView.as_view()),
    path("api/reports/financial-periods/", RmsFinancialPeriodsListView.as_view()),
    # RMS: register before generic path("api/", include(...)) so /api/reports/* always hits this app.
    path("api/reports/", include("ppaa_portal.reports_management_urls")),
    *(
        [path("api/", include("microservices.maoni.urls"))]
        if "microservices.maoni" in settings.INSTALLED_APPS
        else []
    ),
    path("api/", include("ppaa_auth.common_provider_urls")),
    path("api/", include("api.urls")),
    path("api/internal-portal/", include("ppaa_portal.internal_portal_urls")),
    path("api/performance-dashboard/", include("microservices.ppaa_performance.urls")),
    path("token/", MyTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("swagger/", schema_view.with_ui("swagger", cache_timeout=0), name="schema-swagger-ui"),
    path("redoc/", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"),
    re_path(
        r"^swagger(?P<format>\.json|\.yaml)$",
        schema_view.without_ui(cache_timeout=0),
        name="schema-json",
    ),
]
