from rest_framework.response import  Response
from rest_framework import status
from django.test import TestCase
import math

from ppaa_portal.response_codes import CustomResponse


class CustomPagination(TestCase):
    @staticmethod
    def paginate(view_class, results, request, serializer_context=None):
        paginated = request.GET.get('paginated',False)
        ctx = {"is_auth_view": False, "request": request}
        if serializer_context:
            ctx.update(serializer_context)
        if paginated == True or str(paginated).lower() == 'true':
            page = int(request.GET.get("page", 1))
            page_size = int(request.GET.get("page_size", 10))

            start_num = (page - 1) * page_size
            end_num = page_size * page
            # Handle both QuerySet and list
            total = len(results)

            serializer = view_class.serializer_class(
                results[start_num:end_num],
                many=True,
                context=ctx,
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
            serializer = view_class.serializer_class(
                results,
                many=True,
                context=ctx,
            )

            return CustomResponse.success(
                data=serializer.data,
                message="Success",

            )