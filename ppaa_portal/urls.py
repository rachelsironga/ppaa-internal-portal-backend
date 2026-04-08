"""
URL configuration for eapproval_api project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include, re_path
from rest_framework import permissions
from rest_framework_simplejwt.views import TokenRefreshView


from drf_yasg.views import get_schema_view
from drf_yasg import openapi

from ppaa_auth.utils import MyTokenObtainPairView
from microservices.ppaa_maoni.views import SuggestionView
from .views import (
    DocumentCategoryView,
    DocumentView,
    AnnouncementView,
    EventView,
    FAQView,
    NotificationView,
    TodoListView,
    AuditLogView,
    PublicPPaaDashboardView,
    QuickLinkClickView,
)

schema_view = get_schema_view(
    openapi.Info(
        title="Your API Name",
        default_version='v1',
        description="API documentation",
        terms_of_service="https://yourwebsite.com/terms/",
        contact=openapi.Contact(email="support@yourwebsite.com"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
)


urlpatterns = [
    path('admin/', admin.site.urls),
    path('user/', include('ppaa_auth.urls')),
    # I USE THIS TO ENSURE BUSINESS LOGIC MATCH THE REALITY:  
    # path('api/', include('ppaa_auth.urls')), YOU MAY UNCOMMENT THIS IF THE BUSINESS LOGIC MATCH THE REALITY
    path('api/', include('ppaa_auth.common_provider_urls')),
    path('api/', include('api.urls')),
    path('api/reports/', include('microservices.ppaa_reports.urls')),
    # Support clients that POST to /api/maoni (no trailing slash). Django won't redirect POSTs.
    path('api/maoni', SuggestionView.as_view(), name='maoni-suggestions-root'),
    path('api/maoni/', include('microservices.ppaa_maoni.urls')),

    # Public PPAA Internal Portal dashboard summary (no auth required)
    path('public/ppaa-dashboard/', PublicPPaaDashboardView.as_view(), name='public-ppaa-dashboard'),
    # Public quick link click tracking (no auth required)
    path('public/quick-links/<str:uid>/click/', QuickLinkClickView.as_view(), name='public-quick-link-click'),
   
    path('token/', MyTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),



    # Swagger UI
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),

    # ReDoc UI
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),

    # Raw JSON schema
    re_path(r'^swagger(?P<format>\.json|\.yaml)$', schema_view.without_ui(cache_timeout=0), name='schema-json'),

]
