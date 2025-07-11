from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status

from mnh_approval.response_codes import CustomResponse


def custom_api_exception_handler(exc, context):
    response = exception_handler(exc, context)

    # If it's a 403, replace the response
    if response and response.status_code == 403:
        return CustomResponse.forbidden(
            message="You don’t have permission to access this resource"
        )

    return response