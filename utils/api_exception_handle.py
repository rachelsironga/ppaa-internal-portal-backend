from rest_framework.views import exception_handler
from rest_framework import status
from django.db.utils import ProgrammingError

<<<<<<< HEAD
from ppaa_portal.response_codes import STATUS_CODES


def custom_api_exception_handler(exc, context):
    """
    Wrap DRF's handler. Do not return a brand-new Response for 403: that can skip
    negotiation metadata and later trigger ``.accepted_renderer not set on Response``
    when Django renders the response.
    """
=======
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

>>>>>>> 33e584ef8d8ea737c60e41f28d82991f7405cd92
    response = exception_handler(exc, context)

    if response is not None and response.status_code == status.HTTP_403_FORBIDDEN:
        response.data = {
            "status": STATUS_CODES["FORBIDDEN"],
            "message": "You don’t have permission to access this resource",
            "data": None,
        }

    return response