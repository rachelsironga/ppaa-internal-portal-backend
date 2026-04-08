from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from django.db.utils import ProgrammingError

from ppaa_portal.response_codes import CustomResponse, STATUS_CODES


def custom_api_exception_handler(exc, context):
    # SPISM: missing performance_dashboard tables (migrations not run)
    if isinstance(exc, ProgrammingError) and "does not exist" in str(exc) and "performance_" in str(exc):
        return Response(
            {
                "status": STATUS_CODES["SERVER_ERROR"],
                "message": "Performance (SPISM) database tables are missing. Run: python manage.py migrate --database=performance_dashboard",
                "data": None,
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    response = exception_handler(exc, context)

    # If it's a 403, replace the response
    if response and response.status_code == 403:
        return CustomResponse.forbidden(
            message="You don’t have permission to access this resource"
        )

    return response