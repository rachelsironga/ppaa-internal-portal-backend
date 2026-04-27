from rest_framework.views import exception_handler
from rest_framework import status

from ppaa_portal.response_codes import STATUS_CODES


def custom_api_exception_handler(exc, context):
    """
    Wrap DRF's handler. Do not return a brand-new Response for 403: that can skip
    negotiation metadata and later trigger ``.accepted_renderer not set on Response``
    when Django renders the response.
    """
    response = exception_handler(exc, context)

    if response is not None and response.status_code == status.HTTP_403_FORBIDDEN:
        response.data = {
            "status": STATUS_CODES["FORBIDDEN"],
            "message": "You don’t have permission to access this resource",
            "data": None,
        }

    return response