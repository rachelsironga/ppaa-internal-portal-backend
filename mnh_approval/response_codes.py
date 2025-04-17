from rest_framework.response import Response
from rest_framework import status

STATUS_CODES = {
    "SUCCESSFUL": 8000,
    "DATA_NOT_FOUND": 8001,
    "VALIDATION_ERROR": 8002,
    "PROCESS_FAILED": 8003,
    "SERVER_ERROR": 8005,
    "FORBIDDEN": 8006,
}


class CustomResponse:
    @staticmethod
    def success(data=None, message="Successful", pagination=None):
        if pagination is None:
            pagination = {}
        return Response({
            "status": STATUS_CODES["SUCCESSFUL"],
            "message": message,
            "data": data,
            "pagination" : pagination
        }, status=status.HTTP_200_OK)

    @staticmethod
    def errors(message="Data Not Found", data=None, code=STATUS_CODES["DATA_NOT_FOUND"]):
        return Response({
            "status": code,
            "message": message,
            "data": data
        }, status=status.HTTP_202_ACCEPTED)

    @staticmethod
    def server_error(message="Server Error"):
        return Response({
            "status": STATUS_CODES["SERVER_ERROR"],
            "message": message,
            "data": None
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @staticmethod
    def forbidden(message="Forbidden Access"):
        return Response({
            "status": STATUS_CODES["FORBIDDEN"],
            "message": message,
            "data": None
        }, status=status.HTTP_403_FORBIDDEN)