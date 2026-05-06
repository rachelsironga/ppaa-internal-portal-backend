from django.urls import path

from ppaa_auth.modules.users import UserView
from ppaa_auth.views import DepartmentView

urlpatterns = [
    path("auth/users", UserView.as_view(), name="auth/users"),
    path("auth/users/<str:gui>", UserView.as_view(), name="view_user"),
    path("departments", DepartmentView.as_view(), name="departments"),
    path("departments/<str:uid>", DepartmentView.as_view(), name="view_department"),
]
