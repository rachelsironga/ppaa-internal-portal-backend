from django.urls import path

from mnh_auth.views import UserView, UpdateMyProfileView, LoginView, RegistrationView

# app_name = 'user'

urlpatterns = [
    path('login', LoginView.as_view(), name='auth-login'),
    path('register', RegistrationView.as_view(), name='auth-register'),

    path('profile', UserView.as_view(), name='view-user'),
    path('user/update', UpdateMyProfileView.as_view(), name='update-user')

]