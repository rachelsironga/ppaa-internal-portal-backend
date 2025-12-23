from django.urls import path

from mnh_auth.modules.user_bulk_import import BulkUserImportView
from mnh_auth.modules.user_profile import UserProfileView, ActingUser
from mnh_auth.views import LoginView, RegistrationView, LoginNewUser, ChangePasswordView, ResetPasswordView, CountriesView, CurrenciesView, DirectoryView, DepartmentView, AdminChangePasswordView
from mnh_auth.modules.users import UserView, UserPhotoUpload, UserSignatureUpload

# app_name = 'user'

urlpatterns = [
    path('login', LoginView.as_view(), name='auth-login'),
    path('new_login', LoginNewUser.as_view(), name='new_login'),
    path('register', RegistrationView.as_view(), name='auth-register'),

    path('setup', UserView.as_view(), name='view-user-setup'),
    path('setup-photo', UserPhotoUpload.as_view(), name='user-setup-photo'),
    path('setup-signature', UserSignatureUpload.as_view(), name='user-setup-signature'),
    path('setup/assign-delegated-user', ActingUser.as_view(), name='assign-delegated-user'),
    path('setup/<str:uid>', UserView.as_view(), name='open-user-setup'),
    path('change-password', ChangePasswordView.as_view(), name='user-change-password'),
    path('reset-password', ResetPasswordView.as_view(), name='user-change-password'),
    path('reset-update-password', AdminChangePasswordView.as_view(), name='reset-update-user-password'),

    path('import-user-excel', BulkUserImportView.as_view(), name='import-user-excel'),

    path('countries', CountriesView.as_view(), name='countries'),
    path('currencies', CurrenciesView.as_view(), name='currencies'),

    path('directories', DirectoryView.as_view(), name='directories'),
    path('directories/<str:uid>', DirectoryView.as_view(), name='open-directory'),

    path('departments', DepartmentView.as_view(), name='departments'),
    path('departments/<str:uid>', DepartmentView.as_view(), name='open-department'),




    path('positions', UserProfileView.as_view(), name='positions'),
    path('positions/<str:uid>', UserProfileView.as_view(), name='open-positions'),

]