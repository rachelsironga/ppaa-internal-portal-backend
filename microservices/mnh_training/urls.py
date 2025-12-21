from django.urls import path
from microservices.mnh_training.modules.student import StudentView
from microservices.mnh_training.modules.application import ApplicationView
from microservices.mnh_training.modules.affiliation import AffiliationView
from microservices.mnh_training.modules.institution import InstitutionView
from microservices.mnh_training.modules.mou import MOUView
from microservices.mnh_training.modules.training_batch import TrainingBatchView
from microservices.mnh_training.modules.department_allocation import DepartmentAllocationView
from microservices.mnh_training.modules.supervisor import SupervisorView
from microservices.mnh_training.modules.training_setting import TrainingSettingView

urlpatterns = [
    # Student URLs
    path('students', StudentView.as_view(), name='student-list'),
    path('students/create', StudentView.as_view(), name='student-create'),
    path('students/import', StudentView.as_view(), name='student-import'),
    path('students/<uuid:uid>', StudentView.as_view(), name='student-detail'),
    path('students/<uuid:uid>/update', StudentView.as_view(), name='student-update'),
    path('students/<uuid:uid>/delete', StudentView.as_view(), name='student-delete'),
    
    # Affiliation URLs
    path('affiliations', AffiliationView.as_view(), name='affiliation-list'),
    path('affiliations/create', AffiliationView.as_view(), name='affiliation-create'),
    path('affiliations/<uuid:uid>', AffiliationView.as_view(), name='affiliation-detail'),
    path('affiliations/<uuid:uid>/delete', AffiliationView.as_view(), name='affiliation-delete'),
    
    # Institution URLs
    path('institutions', InstitutionView.as_view(), name='institution-list'),
    path('institutions/create', InstitutionView.as_view(), name='institution-create'),
    path('institutions/<uuid:uid>', InstitutionView.as_view(), name='institution-detail'),
    path('institutions/<uuid:uid>/update', InstitutionView.as_view(), name='institution-update'),
    path('institutions/<uuid:uid>/delete', InstitutionView.as_view(), name='institution-delete'),
    
    # MOU URLs
    path('mous', MOUView.as_view(), name='mou-list'),
    path('mous/create', MOUView.as_view(), name='mou-create'),
    path('mous/<uuid:uid>', MOUView.as_view(), name='mou-detail'),
    path('mous/<uuid:uid>/update', MOUView.as_view(), name='mou-update'),
    path('mous/<uuid:uid>/delete', MOUView.as_view(), name='mou-delete'),
    
    # Training Batch URLs
    path('training-batches', TrainingBatchView.as_view(), name='training-batch-list'),
    path('training-batches/create', TrainingBatchView.as_view(), name='training-batch-create'),
    path('training-batches/<uuid:uid>', TrainingBatchView.as_view(), name='training-batch-detail'),
    path('training-batches/<uuid:uid>/update', TrainingBatchView.as_view(), name='training-batch-update'),
    path('training-batches/<uuid:uid>/delete', TrainingBatchView.as_view(), name='training-batch-delete'),
    
    # Application URLs
    path('applications', ApplicationView.as_view(), name='application-list'),
    path('applications/create', ApplicationView.as_view(), name='application-create'),
    path('applications/<uuid:uid>', ApplicationView.as_view(), name='application-detail'),
    path('applications/<uuid:uid>/update', ApplicationView.as_view(), name='application-update'),
    path('applications/<uuid:uid>/delete', ApplicationView.as_view(), name='application-delete'),
    
    # Department Allocation URLs
    path('department-allocations', DepartmentAllocationView.as_view(), name='department-allocation-list'),
    path('department-allocations/create', DepartmentAllocationView.as_view(), name='department-allocation-create'),
    path('department-allocations/<uuid:uid>', DepartmentAllocationView.as_view(), name='department-allocation-detail'),
    path('department-allocations/<uuid:uid>/update', DepartmentAllocationView.as_view(), name='department-allocation-update'),
    path('department-allocations/<uuid:uid>/delete', DepartmentAllocationView.as_view(), name='department-allocation-delete'),
    
    # Supervisor URLs
    path('supervisors', SupervisorView.as_view(), name='supervisor-list'),
    path('supervisors/create', SupervisorView.as_view(), name='supervisor-create'),
    path('supervisors/<uuid:uid>', SupervisorView.as_view(), name='supervisor-detail'),
    path('supervisors/<uuid:uid>/update', SupervisorView.as_view(), name='supervisor-update'),
    path('supervisors/<uuid:uid>/delete', SupervisorView.as_view(), name='supervisor-delete'),
    
    # Training Settings URLs
    path('settings', TrainingSettingView.as_view(), name='training-setting-get'),
    path('settings/update', TrainingSettingView.as_view(), name='training-setting-update'),
    path('settings/special-departments', TrainingSettingView.as_view(), name='training-setting-special-dept'),
    path('settings/special-departments/<uuid:department_uid>', TrainingSettingView.as_view(), name='training-setting-special-dept-detail'),
]
