from datetime import datetime
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
import base64
from django.template.loader import render_to_string
from weasyprint import HTML
from io import BytesIO

from mnh_approval.response_codes import CustomResponse
from .models import LocationalOxygenUsage
from .serializers import UsageReportSerializer


class OxygenSummaryReportView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UsageReportSerializer
    template_name = 'oxygen_usage_report.html'

    def get(self, request, date_from: str, date_to: str):
        try:
            # Parse dates
            try:
                date_from = timezone.datetime.strptime(date_from.strip(), "%Y-%m-%d")
                date_to = timezone.datetime.strptime(date_to.strip(), "%Y-%m-%d")
            except ValueError:
                return CustomResponse.errors(message="Please provide date range with format YYYY-MM-DD")

            search_query = request.GET.get('search', '').strip()
            location = request.GET.get('location', '').strip()
            report_type = request.GET.get('report_type', 'simple').strip()

            location_usage = LocationalOxygenUsage.objects.filter(
                date__date__range=(date_from, date_to),
                is_deleted=False
            )

            # Fetch usage data with prefetch_related to optimize queries
            location_usage = LocationalOxygenUsage.objects.filter(
                date__date__range=(date_from, date_to),
                is_deleted=False
            ).prefetch_related(
                'patient_age_groups',
                'patient_age_groups__patient_age_group',
                'location'
            )

            if not location_usage.exists():
                return CustomResponse.errors(message="Oxygen Allocation not found", data=[])

            # Calculate totals for each record
            usage_data = []
            for usage in location_usage:
                total_oxygen = sum([age_group.oxygen for age_group in usage.patient_age_groups.all()])
                total_ventilator = sum([age_group.ventilator for age_group in usage.patient_age_groups.all()])
                total_cpap = sum([age_group.cpap for age_group in usage.patient_age_groups.all()])
                total_patients = total_oxygen + total_ventilator + total_cpap

                usage_data.append({
                    'date': usage.date,
                    'location': usage.location.name,
                    'total_patients': total_patients,
                    'total_oxygen': total_oxygen,
                    'total_ventilator': total_ventilator,
                    'total_cpap': total_cpap,
                })

            # --- Age Group Summary ---
            age_group_summary = {}
            for usage in location_usage:
                for age_usage in usage.patient_age_groups.all():
                    group_name = age_usage.patient_age_group.name
                    if group_name not in age_group_summary:
                        age_group_summary[group_name] = {
                            'total': 0,
                            'oxygen': 0,
                            'ventilator': 0,
                            'cpap': 0
                        }
                    age_group_summary[group_name]['oxygen'] += age_usage.oxygen
                    age_group_summary[group_name]['ventilator'] += age_usage.ventilator
                    age_group_summary[group_name]['cpap'] += age_usage.cpap
                    age_group_summary[group_name]['total'] += age_usage.oxygen + age_usage.ventilator + age_usage.cpap

            # Calculate Grand Totals
            grand_totals = {
                'total': sum(item['oxygen'] + item['ventilator'] + item['cpap'] for item in age_group_summary.values()),
                'oxygen': sum(item['oxygen'] for item in age_group_summary.values()),
                'ventilator': sum(item['ventilator'] for item in age_group_summary.values()),
                'cpap': sum(item['cpap'] for item in age_group_summary.values())
            }

            # Prepare PDF Context using WeasyPrint
            context = {
                'date_from': date_from,
                'date_to': date_to,
                'usages': usage_data,
                'age_group_summary': age_group_summary,
                'grand_totals': grand_totals
            }

            # Generate PDF
            html_string = render_to_string(self.template_name, context)
            pdf_buffer = BytesIO()
            HTML(string=html_string).write_pdf(pdf_buffer)
            pdf_bytes = pdf_buffer.getvalue()

            # Encode PDF to base64
            base64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')

            # Serialize the data with the base64 PDF
            serializer = self.serializer_class(location_usage, many=True)
            data = serializer.data

            # Inject base64 PDF into the first item (or return as global value)
            if data:
                data[0]['report_file'] = base64_pdf  # Or add at the end as {'report_file': base64_pdf}

            return CustomResponse.success(data={
                "base64": base64_pdf
            })

        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Retrieve Oxygen Allocations: {str(e)}')