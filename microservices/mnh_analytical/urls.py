from django.urls import path

from microservices.mnh_analytical.modules.block import BlockView
from microservices.mnh_analytical.modules.clinic import ClinicView, BulkClinicImportView
from microservices.mnh_analytical.modules.payment_mode import PaymentModeView
from microservices.mnh_analytical.modules.attendance import (
    AttendanceView, AttendanceSummaryView, AttendanceUploadView, ProcessAttendanceView
)
from microservices.mnh_analytical.modules.patient_attendance import (
    PatientAttendanceView, PatientAttendanceBulkCreateView, ClinicPatientVolumeView
)
from microservices.mnh_analytical.modules.dashboard import (
    AnalyticalDashboardView, PatientTrendView, PaymentModeDistributionView, BlockClinicDistributionView,
    ClinicGrowthTrendsView, DepartmentClinicComparisonView
)


urlpatterns = [
    # Block URLs
    path('blocks', BlockView.as_view(), name='block-list'),
    path('blocks/create', BlockView.as_view(), name='block-create'),
    path('blocks/<uuid:uid>', BlockView.as_view(), name='block-detail'),
    path('blocks/<uuid:uid>/update', BlockView.as_view(), name='block-update'),
    path('blocks/<uuid:uid>/delete', BlockView.as_view(), name='block-delete'),

    # Clinic URLs
    path('clinics', ClinicView.as_view(), name='clinic-list'),
    path('clinics/create', ClinicView.as_view(), name='clinic-create'),
    path('clinics/import', BulkClinicImportView.as_view(), name='clinic-import'),
    path('clinics/<uuid:uid>', ClinicView.as_view(), name='clinic-detail'),
    path('clinics/<uuid:uid>/update', ClinicView.as_view(), name='clinic-update'),
    path('clinics/<uuid:uid>/delete', ClinicView.as_view(), name='clinic-delete'),

    # Payment Mode URLs
    path('payment-modes', PaymentModeView.as_view(), name='payment-mode-list'),
    path('payment-modes/create', PaymentModeView.as_view(), name='payment-mode-create'),
    path('payment-modes/<uuid:uid>', PaymentModeView.as_view(), name='payment-mode-detail'),
    path('payment-modes/<uuid:uid>/update', PaymentModeView.as_view(), name='payment-mode-update'),
    path('payment-modes/<uuid:uid>/delete', PaymentModeView.as_view(), name='payment-mode-delete'),

    # Attendance URLs
    path('attendances', AttendanceView.as_view(), name='attendance-list'),
    path('attendances/create', AttendanceView.as_view(), name='attendance-create'),
    path('attendances/upload', AttendanceUploadView.as_view(), name='attendance-upload'),
    path('attendances/summary', AttendanceSummaryView.as_view(), name='attendance-summary'),
    path('attendances/<uuid:uid>', AttendanceView.as_view(), name='attendance-detail'),
    path('attendances/<uuid:uid>/update', AttendanceView.as_view(), name='attendance-update'),
    path('attendances/<uuid:uid>/process', ProcessAttendanceView.as_view(), name='attendance-process'),
    path('attendances/<uuid:uid>/delete', AttendanceView.as_view(), name='attendance-delete'),

    # Patient Attendance URLs
    path('patient-attendances', PatientAttendanceView.as_view(), name='patient-attendance-list'),
    path('patient-attendances/create', PatientAttendanceView.as_view(), name='patient-attendance-create'),
    path('patient-attendances/bulk-create', PatientAttendanceBulkCreateView.as_view(), name='patient-attendance-bulk-create'),
    path('patient-attendances/<uuid:uid>', PatientAttendanceView.as_view(), name='patient-attendance-detail'),
    path('patient-attendances/<uuid:uid>/update', PatientAttendanceView.as_view(), name='patient-attendance-update'),
    path('patient-attendances/<uuid:uid>/delete', PatientAttendanceView.as_view(), name='patient-attendance-delete'),

    # Analytics/Dashboard URLs
    path('dashboard', AnalyticalDashboardView.as_view(), name='analytical-dashboard'),
    path('dashboard/patient-trends', PatientTrendView.as_view(), name='patient-trends'),
    path('dashboard/payment-distribution', PaymentModeDistributionView.as_view(), name='payment-distribution'),
    path('dashboard/block-clinic-distribution', BlockClinicDistributionView.as_view(), name='block-clinic-distribution'),
    path('dashboard/clinic-volumes', ClinicPatientVolumeView.as_view(), name='clinic-volumes'),
    path('dashboard/clinic-growth-trends', ClinicGrowthTrendsView.as_view(), name='clinic-growth-trends'),
    path('dashboard/department-clinic-comparison', DepartmentClinicComparisonView.as_view(), name='department-clinic-comparison'),
]
