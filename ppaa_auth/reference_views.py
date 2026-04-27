from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from ppaa_auth.models import Country, Currency
from ppaa_portal.response_codes import CustomResponse


class CountriesListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Country.objects.filter(is_deleted=False).order_by("name")
        rows = []
        for c in qs[:5000]:
            iso = getattr(c, "iso_code", None) or getattr(c, "code", None)
            rows.append({"uid": str(c.uid), "name": c.name, "iso_code": iso})
        return CustomResponse.success(data=rows)


class CurrenciesListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Currency.objects.all().order_by("name")
        rows = [
            {"uid": str(c.uid), "name": c.name, "code": getattr(c, "code", "")}
            for c in qs[:500]
        ]
        return CustomResponse.success(data=rows)
