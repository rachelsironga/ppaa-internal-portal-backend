from rest_framework.response import  Response
from rest_framework import status
from django.test import TestCase
import math

from mnh_approval.response_codes import CustomResponse


class CustomPagination(TestCase):
    @staticmethod
    def paginate(view_class, results, request, serializer_context):
        paginated = request.GET.get('paginated',False)
        if paginated == True or str(paginated).lower() == 'true':
            page = int(request.GET.get("page", 1))
            page_size = int(request.GET.get("page_size", 10))

            start_num = (page - 1) * page_size
            end_num = page_size * page
            total = results.count()
            serializer = view_class.serializer_class(
                results[start_num:end_num],
                many=True,
                context={"is_auth_view": False},
            )

            return CustomResponse.success(
                data=serializer.data,
                message="Success",
                pagination={
                    "page_size": page_size,
                    "page": page,
                    "total": total,
                }
            )

        else:
            serializer = view_class.serializer_class(results, many=True, context=serializer_context)
            return CustomResponse.success(
                data=serializer.data,
                message="Success",
            )