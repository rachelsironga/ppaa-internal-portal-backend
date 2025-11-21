from django.urls import path

from .modules.locational_oxygen_usage import LocationalOxygenUsageView
from .modules.oxygen_allocation import OxygenAllocationView, OxygenAllocationVerifyView
from .modules.oxygen_receiving import OxygenReceivingVerifyView, OxygenReceivingView
from .modules.location import LocationView
from .modules.location_oxygen_volume import LocationOxygenVolumesView
from .modules.oxygen_volume import OxygenVolumeView
from .modules.patient_age_group import PatientAgeGroupView
from .modules.supplier import SupplierView
from .views import OxygenSummaryReportView

urlpatterns = [
    
    path('suppliers', SupplierView.as_view(), name='all-supplier'),
    path('suppliers/<str:uid>', SupplierView.as_view(), name='one-supplier'),
    
    path('location', LocationView.as_view(), name='all-location'),
    path('location/<str:uid>', LocationView.as_view(), name='one-location'),

    path('location-oxygen-volumes', LocationOxygenVolumesView.as_view(), name='all-location-oxygen-volumes'),
    path('location-oxygen-volumes/<str:uid>', LocationOxygenVolumesView.as_view(), name='one-location-oxygen-volumes'),
    
    path('oxygen-volumes', OxygenVolumeView.as_view(), name='all-oxygen-volumes'),
    path('oxygen-volumes/<str:uid>', OxygenVolumeView.as_view(), name='one-oxygen-volumes'),
    
    path('oxygen-receivings', OxygenReceivingView.as_view(), name='all-oxygen-receiving'),
    path('oxygen-receivings/<str:uid>', OxygenReceivingView.as_view(), name='one-oxygen-receiving'),
    path('oxygen-receiving-verify/<str:uid>', OxygenReceivingVerifyView.as_view(), name='oxygen-receiving-verify'),


    path('oxygen-allocations', OxygenAllocationView.as_view(), name='all-oxygen-allocation'),
    path('oxygen-allocations/<str:uid>', OxygenAllocationView.as_view(), name='one-oxygen-allocation'),
    path('oxygen-allocation-verify/<str:uid>', OxygenAllocationVerifyView.as_view(), name='oxygen-allocation-verify'),

    path('patient-age-groups', PatientAgeGroupView.as_view(), name='all-patient-age-group'),
    path('patient-age-groups/<str:uid>', PatientAgeGroupView.as_view(), name='one-patient-age-group'),

    path('locational-oxygen-usages', LocationalOxygenUsageView.as_view(), name='all-locational-oxygen-usage'),
    path('locational-oxygen-usages/<str:uid>', LocationalOxygenUsageView.as_view(), name='one-locational-oxygen-usage'),

    # Reports
    path('oxygen-usage-report/<str:date_from>/<str:date_to>', OxygenSummaryReportView.as_view(), name='oxygen-usage-report'),

]