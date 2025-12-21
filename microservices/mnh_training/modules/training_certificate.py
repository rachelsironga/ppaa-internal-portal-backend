# training_certificate.py
from datetime import datetime
from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from microservices.mnh_training.models import TrainingCertificate, TrainingBatch, TrainingSetting
from microservices.mnh_training.serializers import TrainingCertificateSerializer, TrainingCertificateListSerializer
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from utils.permissions import HasMethodPermission


class TrainingCertificateView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = TrainingCertificateSerializer
    list_serializer_class = TrainingCertificateListSerializer

    required_permissions = {
        "get": ["view_trainingcertificate"],
        "post": ["add_trainingcertificate", "change_trainingcertificate"],
        "put": ["change_trainingcertificate"],
        "patch": ["change_trainingcertificate"],
        "delete": ["delete_trainingcertificate"],
    }

    def get(self, request, uid=None):
        try:
            if uid:
                certificate = TrainingCertificate.objects.filter(uid=uid, is_deleted=False).first()
                if not certificate:
                    raise NotFound("Training certificate not found")
                return CustomResponse.success(data=self.serializer_class(certificate).data)

            batch_uid = request.GET.get('batch_uid', '').strip()
            certificate_number = request.GET.get('certificate_number', '').strip()
            status = request.GET.get('status', '').strip()

            certificates = TrainingCertificate.objects.filter(is_deleted=False)

            if batch_uid:
                certificates = certificates.filter(batch__uid=batch_uid)

            if certificate_number:
                certificates = certificates.filter(certificate_number__icontains=certificate_number)

            if status:
                certificates = certificates.filter(status=status)

            if certificates.exists():
                serializer = self.list_serializer_class(
                    certificates.order_by('-issue_date'),
                    many=True,
                    context={'request': request}
                )
                return CustomResponse.success(data=serializer.data)

            return CustomResponse.errors(message="Certificates not found", data=[])

        except Exception as e:
            return CustomResponse.server_error(
                message=f'Failed to Retrieve Certificates: {str(e)}'
            )

    def post(self, request):
        try:
            with transaction.atomic():
                uid = request.data.get('uid')

                if uid:
                    instance = TrainingCertificate.objects.filter(uid=uid, is_deleted=False).first()
                    if not instance:
                        return CustomResponse.errors(message="Certificate not found")

                    serializer = self.serializer_class(
                        instance,
                        data=request.data,
                        partial=True,
                        context={'request': request}
                    )
                else:
                    serializer = self.serializer_class(
                        data=request.data,
                        context={'request': request}
                    )

                if serializer.is_valid():
                    serializer.save()
                    return CustomResponse.success(data=serializer.data)

                return CustomResponse.errors(
                    message="Validation Failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )

        except Exception as e:
            return CustomResponse.server_error(
                message=f'Failed to Create/Update Certificate: {str(e)}'
            )

    def put(self, request, uid):
        try:
            with transaction.atomic():
                instance = TrainingCertificate.objects.filter(uid=uid, is_deleted=False).first()
                if not instance:
                    return CustomResponse.errors(message="Certificate not found")

                serializer = self.serializer_class(
                    instance,
                    data=request.data,
                    partial=False,
                    context={'request': request}
                )

                if serializer.is_valid():
                    serializer.save()
                    return CustomResponse.success(data=serializer.data)

                return CustomResponse.errors(
                    message="Validation Failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )

        except Exception as e:
            return CustomResponse.server_error(
                message=f'Failed to Update Certificate: {str(e)}'
            )

    def patch(self, request, uid):
        try:
            with transaction.atomic():
                instance = TrainingCertificate.objects.filter(uid=uid, is_deleted=False).first()
                if not instance:
                    return CustomResponse.errors(message="Certificate not found")

                serializer = self.serializer_class(
                    instance,
                    data=request.data,
                    partial=True,
                    context={'request': request}
                )

                if serializer.is_valid():
                    serializer.save()
                    return CustomResponse.success(data=serializer.data)

                return CustomResponse.errors(
                    message="Validation Failed",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )

        except Exception as e:
            return CustomResponse.server_error(
                message=f'Failed to Partially Update Certificate: {str(e)}'
            )

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                certificate = TrainingCertificate.objects.filter(uid=uid, is_deleted=False).first()
                if not certificate:
                    return CustomResponse.errors(message="Certificate not found or already deleted")

                certificate.is_deleted = True
                certificate.deleted_at = datetime.now()
                certificate.deleted_by = request.user
                certificate.save()

                return CustomResponse.success(message='Certificate deleted successfully')

        except Exception as e:
            return CustomResponse.server_error(
                message="Something went wrong while deleting certificate"
            )

    def issue_certificate(self, request, uid):
        """Issue a certificate to a participant"""
        try:
            with transaction.atomic():
                certificate = TrainingCertificate.objects.filter(uid=uid, is_deleted=False).first()
                if not certificate:
                    return CustomResponse.errors(message="Certificate not found")

                if certificate.status != TrainingCertificate.CertificateStatus.DRAFT:
                    return CustomResponse.errors(
                        message=f"Only draft certificates can be issued (current status: {certificate.get_status_display()})"
                    )

                # Update certificate status
                certificate.status = TrainingCertificate.CertificateStatus.ISSUED
                certificate.issue_date = datetime.now().date()
                certificate.issued_by_guid = str(request.user.id)

                # Set expiry date if configured
                settings = TrainingSetting.get_settings()
                if settings.certificate_validity_years > 0:
                    from datetime import timedelta, date
                    certificate.expiry_date = certificate.issue_date + timedelta(days=365 * settings.certificate_validity_years)

                certificate.save()

                serializer = self.serializer_class(certificate, context={'request': request})
                return CustomResponse.success(
                    data=serializer.data,
                    message="Certificate issued successfully"
                )

        except Exception as e:
            return CustomResponse.server_error(
                message=f'Failed to Issue Certificate: {str(e)}'
            )

    def revoke_certificate(self, request, uid):
        """Revoke an issued certificate"""
        try:
            with transaction.atomic():
                certificate = TrainingCertificate.objects.filter(uid=uid, is_deleted=False).first()
                if not certificate:
                    return CustomResponse.errors(message="Certificate not found")

                if certificate.status != TrainingCertificate.CertificateStatus.ISSUED:
                    return CustomResponse.errors(
                        message="Only issued certificates can be revoked"
                    )

                revocation_reason = request.data.get('revocation_reason', '')

                certificate.status = TrainingCertificate.CertificateStatus.REVOKED
                certificate.revoked_by_guid = str(request.user.id)
                certificate.revocation_reason = revocation_reason
                certificate.save()

                serializer = self.serializer_class(certificate, context={'request': request})
                return CustomResponse.success(
                    data=serializer.data,
                    message="Certificate revoked successfully"
                )

        except Exception as e:
            return CustomResponse.server_error(
                message=f'Failed to Revoke Certificate: {str(e)}'
            )
