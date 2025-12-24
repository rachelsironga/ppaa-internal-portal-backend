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

from mnh_auth.utils import MyTokenObtainPairView

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
    path('user/', include('mnh_auth.urls')),
    # I USE THIS TO ENSURE BUSINESS LOGIC MATCH THE REALITY:  
    # path('api/', include('mnh_auth.urls')), YOU MAY UNCOMMENT THIS IF THE BUSINESS LOGIC MATCH THE REALITY
    path('api/', include('mnh_auth.common_provider_urls')),
    path('api/', include('api.urls')),
    path('api/oxygen/', include('microservices.oxygen_managements.urls')),
    path('api/', include('microservices.ict_assets.urls')),
    path('api/analytical/', include('microservices.mnh_analytical.urls')),
    path('api/training/', include('microservices.mnh_training.urls')),
    path('token/', MyTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/', include('microservices.external_referral.urls')),



    # Swagger UI
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),

    # ReDoc UI
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),

    # Raw JSON schema
    re_path(r'^swagger(?P<format>\.json|\.yaml)$', schema_view.without_ui(cache_timeout=0), name='schema-json'),

]
