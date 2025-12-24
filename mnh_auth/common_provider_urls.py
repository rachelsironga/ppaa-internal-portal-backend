from django.urls import path

from mnh_auth.views import CountriesView, CurrenciesView, DirectoryView, DepartmentView
from mnh_auth.modules.users import UserView


urlpatterns = [

    path('auth/users', UserView.as_view(), name='users'),
    path('auth/users/<str:gui>', UserView.as_view(), name='view_user'),
  
    path('countries', CountriesView.as_view(), name='countries'),
    path('countries/<str:uid>', CountriesView.as_view(), name='view_country'),

    path('currencies', CurrenciesView.as_view(), name='currencies'),
    path('currencies/<str:uid>', CurrenciesView.as_view(), name='view_currency'),
    
    path('directories', DirectoryView.as_view(), name='directories'),
    path('directories/<str:uid>', DirectoryView.as_view(), name='view_directory'),
    
    path('departments', DepartmentView.as_view(), name='departments'),
    path('departments/<str:uid>', DepartmentView.as_view(), name='view_department'),

] 