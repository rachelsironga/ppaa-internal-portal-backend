# disposal_record.py
from datetime import datetime, date
from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from microservices.ict_assets.models import (
    Asset,
    DisposalRecord,
    DisposalAuditTrail,
    DisposalConversation,
)
from microservices.ict_assets.serializers import (
    DisposalRecordSerializer,
    DisposalRecordDetailSerializer,
    DisposalAuditTrailSerializer,
    DisposalConversationSerializer,
)
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES
from utils.permissions import HasMethodPermission


def create_audit_trail(disposal_record, action, user, comments=""):
    """Helper function to create an audit trail entry"""
    DisposalAuditTrail.objects.create(
        disposal_record=disposal_record,
        action=action,
        performed_by=user,
        comments=comments,
        created_by=user,
        updated_by=user,
    )


class DisposalRecordView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = DisposalRecordSerializer
    required_permissions = {
        "get": [
            "view_disposalrecord"
        ],
        "post": [
            "add_disposalrecord",
            "change_disposalrecord",
        ],
        "delete": [
            "delete_disposalrecord",
        ]
    }

    def get(self, request, uid=None):
        try:
            if uid:
                disposal_record = DisposalRecord.objects.filter(
                    uid=uid, is_deleted=False
                ).select_related(
                    'asset', 'asset__asset_type', 'asset__manufacturer', 'asset__supplier', 
                    'asset__location', 'asset__custodian', 'approved_by', 'rejected_by'
                ).first()
                if not disposal_record:
                    raise NotFound("Disposal Record not found")
                return CustomResponse.success(data=DisposalRecordDetailSerializer(disposal_record, context={"request": request}).data)

            search_query = request.GET.get('search', '').strip()
            asset_uid = request.GET.get('asset', '').strip()
            disposal_method = request.GET.get('disposal_method', '').strip()
            status = request.GET.get('status', '').strip()
            is_active = request.GET.get('is_active', '').strip()

            print("Disposal Record View", asset_uid, disposal_method, status, is_active, search_query)
            # disposal_records = DisposalRecord.objects.filter(is_deleted=False).order_by('-created_at')

            
            disposal_records = DisposalRecord.objects.filter(is_deleted=False).select_related(
                'asset', 'asset__asset_type', 'asset__manufacturer', 'asset__supplier', 
                'asset__location', 'asset__custodian', 'approved_by', 'rejected_by'
            )

            print("======================DisposalRecord============================>")

            if asset_uid:
                disposal_records = disposal_records.filter(asset__uid=asset_uid)

            if disposal_method:
                # Handle multiple values (e.g., "recycled,sold")
                methods = [m.strip() for m in disposal_method.split(',') if m.strip()]
                if methods:
                    disposal_records = disposal_records.filter(disposal_method__in=methods)

            if status:
                # Handle multiple values (e.g., "pending,approved")
                statuses = [s.strip() for s in status.split(',') if s.strip()]
                if statuses:
                    disposal_records = disposal_records.filter(status__in=statuses)

            if is_active:
                # Handle is_active filter (convert string to boolean)
                if is_active.lower() == 'true':
                    disposal_records = disposal_records.filter(is_active=True)
                elif is_active.lower() == 'false':
                    disposal_records = disposal_records.filter(is_active=False)

            if search_query:
                disposal_records = disposal_records.filter(
                    Q(asset__asset_tag__icontains=search_query) | 
                    Q(disposal_reason__icontains=search_query) |
                    Q(approved_by__first_name__icontains=search_query) |
                    Q(approved_by__last_name__icontains=search_query) |
                    Q(notes__icontains=search_query)
                )

            # Use detail serializer to include full asset object
            paginated = request.GET.get('paginated', False)
            if paginated == True or str(paginated).lower() == 'true':
                page = int(request.GET.get("page", 1))
                page_size = int(request.GET.get("page_size", 10))
                start_num = (page - 1) * page_size
                end_num = page_size * page
                total = disposal_records.count()
                
                serializer = DisposalRecordDetailSerializer(
                    disposal_records[start_num:end_num],
                    many=True,
                    context={"request": request},
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
                serializer = DisposalRecordDetailSerializer(
                    disposal_records,
                    many=True,
                    context={"request": request},
                )
                return CustomResponse.success(data=serializer.data, message="Success")
        except Exception as e:
            print("======================")
            print(f'Failed to Retrieve Disposal Records: {str(e)}')
            return CustomResponse.server_error(message=f'Failed to Retrieve Disposal Records: {str(e)}')

    def post(self, request):
        try:
            with transaction.atomic():
                uid = request.data.get('uid', None)
                asset_uid = request.data.get('asset_uid', None)
                is_update = False
                is_resubmit = False
                instance = None
                
                if uid:
                    # Direct update by UID
                    try:
                        instance = DisposalRecord.objects.get(uid=uid, is_deleted=False)
                        
                        # Check if this is a rejected record being edited
                        # If so, treat it as a resubmission
                        if instance.status == 'rejected':
                            is_resubmit = True
                            # Prepare data with reset fields
                            request_data = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)
                            request_data['status'] = 'pending'
                            request_data['approved_by'] = None
                            request_data['rejected_by'] = None
                            request_data['rejection_reason'] = ''
                            request_data['decision_date'] = None
                            serializer = self.serializer_class(instance, data=request_data, partial=True, context={'request': request})
                        else:
                            serializer = self.serializer_class(instance, data=request.data, partial=True, context={'request': request})
                        
                        is_update = True
                    except DisposalRecord.DoesNotExist:
                        return CustomResponse.errors(message="Disposal Record not found")
                else:
                    # Creating new - check if asset already has a disposal record
                    if asset_uid:
                        try:
                            asset = Asset.objects.get(uid=asset_uid, is_deleted=False)
                            # Check for existing disposal record for this asset
                            existing = DisposalRecord.objects.filter(asset=asset).first()
                            
                            if existing:
                                # Check if we can reuse this record
                                if existing.status == 'rejected':
                                    # Reuse the existing record - reset approval fields
                                    instance = existing
                                    is_update = True
                                    is_resubmit = True
                                    
                                    # Prepare data with reset fields
                                    request_data = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)
                                    request_data['status'] = 'pending'
                                    request_data['approved_by'] = None
                                    request_data['rejected_by'] = None
                                    request_data['rejection_reason'] = ''
                                    request_data['decision_date'] = None
                                    
                                    # If it was soft-deleted, restore it
                                    if existing.is_deleted:
                                        existing.is_deleted = False
                                        existing.deleted_at = None
                                        existing.deleted_by = None
                                        existing.save()
                                    
                                    serializer = self.serializer_class(instance, data=request_data, partial=True, context={'request': request})
                                elif existing.status == 'pending':
                                    return CustomResponse.errors(
                                        message="This asset already has a pending disposal request. Please wait for it to be processed or cancel it first."
                                    )
                                elif existing.status == 'approved':
                                    return CustomResponse.errors(
                                        message="This asset already has an approved disposal record and cannot be disposed again."
                                    )
                                else:
                                    return CustomResponse.errors(
                                        message=f"This asset already has an active disposal request with status: {existing.status}"
                                    )
                            else:
                                serializer = self.serializer_class(data=request.data, context={'request': request})
                        except Asset.DoesNotExist:
                            # Let serializer handle the validation
                            serializer = self.serializer_class(data=request.data, context={'request': request})
                    else:
                        serializer = self.serializer_class(data=request.data, context={'request': request})

                if serializer.is_valid():
                    disposal_record = serializer.save()
                    
                    # Create audit trail entry
                    if is_resubmit:
                        create_audit_trail(
                            disposal_record=disposal_record,
                            action="Resubmitted",
                            user=request.user,
                                    comments=f"Disposal record resubmitted by {request.user.get_full_name() or request.user.username}. Previous rejection has been cleared."
                        )
                        # Add conversation entry for resubmission
                        DisposalConversation.objects.create(
                            disposal_record=disposal_record,
                            sender=request.user,
                            message=f"**Disposal Request Resubmitted**\n\nA new disposal request has been submitted for this asset after the previous request was rejected/cancelled.\n\nReason: {request.data.get('disposal_reason', 'Not specified')}",
                            message_type='request',
                            created_by=request.user,
                            updated_by=request.user,
                        )
                    elif is_update:
                        create_audit_trail(
                            disposal_record=disposal_record,
                            action="Updated",
                            user=request.user,
                            comments=f"Disposal record updated by {request.user.get_full_name() or request.user.username}"
                        )
                    else:
                        create_audit_trail(
                            disposal_record=disposal_record,
                            action="Created",
                            user=request.user,
                            comments=f"Disposal record created by {request.user.get_full_name() or request.user.username}"
                        )
                    
                    return CustomResponse.success(data=serializer.data)

                return CustomResponse.errors(
                    message="Validation Failed, Please Try Again",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )

        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Change Disposal Record: {str(e)}')

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                disposal_record = DisposalRecord.objects.filter(uid=uid, is_deleted=False).first()
                if not disposal_record:
                    return CustomResponse.errors(message="Disposal Record Not Found or Already Deleted")

                # Create audit trail before deletion
                create_audit_trail(
                    disposal_record=disposal_record,
                    action="Deleted",
                    user=request.user,
                    comments=f"Disposal record deleted by {request.user.get_full_name() or request.user.username}"
                )

                disposal_record.is_deleted = True
                disposal_record.deleted_at = datetime.now()
                disposal_record.deleted_by = request.user
                disposal_record.save()
                return CustomResponse.success(message='Disposal Record deleted successfully')

        except Exception as e:
            return CustomResponse.server_error(message="Something went wrong While Deleting Disposal Record")


class DisposalAuditTrailView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = DisposalAuditTrailSerializer
    required_permissions = {
        "get": ["view_disposalaudittrail"],
        "post": ["add_disposalaudittrail"],
    }

    def _get_disposal_record(self, uid):
        disposal_record = DisposalRecord.objects.filter(uid=uid, is_deleted=False).first()
        if not disposal_record:
            raise NotFound("Disposal Record not found")
        return disposal_record

    def get(self, request, uid=None):
        try:
            if not uid:
                return CustomResponse.errors(message="Disposal Record UID is required")

            disposal_record = self._get_disposal_record(uid)
            audit_qs = DisposalAuditTrail.objects.filter(
                disposal_record=disposal_record
            ).select_related("performed_by", "created_by").order_by("-action_date")

            if audit_qs.exists():
                return CustomPagination.paginate(
                    view_class=self, results=audit_qs, request=request
                )

            return CustomResponse.success(message="No audit trail found", data=[])
        except NotFound as e:
            return CustomResponse.errors(message=str(e))
        except Exception as e:
            return CustomResponse.server_error(
                message=f"Failed to retrieve disposal audit trail: {str(e)}"
            )

    def post(self, request, uid=None):
        try:
            if not uid:
                return CustomResponse.errors(message="Disposal Record UID is required")

            disposal_record = self._get_disposal_record(uid)
            serializer = self.serializer_class(
                data=request.data, context={"request": request}
            )

            if serializer.is_valid():
                serializer.save(
                    disposal_record=disposal_record,
                    performed_by=request.user,
                )
                return CustomResponse.success(data=serializer.data)

            return CustomResponse.errors(
                message="Validation Failed, Please Try Again",
                data=serializer.errors,
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        except NotFound as e:
            return CustomResponse.errors(message=str(e))
        except Exception as e:
            return CustomResponse.server_error(
                message=f"Failed to create disposal audit trail: {str(e)}"
            )


class DisposalConversationView(APIView):
    permission_classes = [IsAuthenticated, HasMethodPermission]
    serializer_class = DisposalConversationSerializer
    required_permissions = {
        "get": ["view_disposalconversation"],
        "post": ["add_disposalconversation"],
    }

    def _get_disposal_record(self, uid):
        disposal_record = DisposalRecord.objects.filter(uid=uid, is_deleted=False).first()
        if not disposal_record:
            raise NotFound("Disposal Record not found")
        return disposal_record

    def get(self, request, uid=None):
        try:
            if not uid:
                return CustomResponse.errors(message="Disposal Record UID is required")

            disposal_record = self._get_disposal_record(uid)

            # TODO: apply is_internal filtering based on user role if needed
            conversations = DisposalConversation.objects.filter(
                disposal_record=disposal_record
            ).select_related("sender", "created_by").order_by("created_at")

            if conversations.exists():
                return CustomPagination.paginate(
                    view_class=self, results=conversations, request=request
                )

            return CustomResponse.success(message="No conversations found", data=[])
        except NotFound as e:
            return CustomResponse.errors(message=str(e))
        except Exception as e:
            return CustomResponse.server_error(
                message=f"Failed to retrieve disposal conversations: {str(e)}"
            )

    def post(self, request, uid=None):
        try:
            if not uid:
                return CustomResponse.errors(message="Disposal Record UID is required")

            disposal_record = self._get_disposal_record(uid)
            serializer = self.serializer_class(
                data=request.data, context={"request": request}
            )

            if serializer.is_valid():
                serializer.save(
                    disposal_record=disposal_record,
                    sender=request.user,
                )
                return CustomResponse.success(data=serializer.data)

            return CustomResponse.errors(
                message="Validation Failed, Please Try Again",
                data=serializer.errors,
                code=STATUS_CODES["VALIDATION_ERROR"],
            )
        except NotFound as e:
            return CustomResponse.errors(message=str(e))
        except Exception as e:
            return CustomResponse.server_error(
                message=f"Failed to create disposal conversation: {str(e)}"
            )


class DisposalApprovalView(APIView):
    """View for approving and rejecting disposal records"""
    permission_classes = [IsAuthenticated, HasMethodPermission]
    required_permissions = {
        "post": [
            "approve_disposal_record",
            "reject_disposal_record",
        ],
    }

    def _get_disposal_record(self, uid):
        disposal_record = DisposalRecord.objects.filter(uid=uid, is_deleted=False).first()
        if not disposal_record:
            raise NotFound("Disposal Record not found")
        return disposal_record

    def post(self, request, uid=None, action=None):
        """
        Handle approval or rejection of a disposal record.
        
        action: 'approve' or 'reject'
        """
        try:
            if not uid:
                return CustomResponse.errors(message="Disposal Record UID is required")

            if action not in ['approve', 'reject']:
                return CustomResponse.errors(message="Invalid action. Use 'approve' or 'reject'")

            with transaction.atomic():
                disposal_record = self._get_disposal_record(uid)

                # Check if already processed
                if disposal_record.status != 'pending':
                    return CustomResponse.errors(
                        message=f"This disposal record has already been {disposal_record.status}. Cannot {action} again."
                    )

                if action == 'approve':
                    # Approve the disposal record
                    disposal_record.status = 'approved'
                    disposal_record.approved_by = request.user
                    disposal_record.decision_date = date.today()
                    disposal_record.updated_by = request.user
                    disposal_record.save()

                    # Create audit trail
                    comments = request.data.get('comments', '') or request.data.get('notes', '')
                    create_audit_trail(
                        disposal_record=disposal_record,
                        action="Approved",
                        user=request.user,
                        comments=comments or f"Disposal record approved by {request.user.get_full_name() or request.user.username}"
                    )

                    return CustomResponse.success(
                        data=DisposalRecordDetailSerializer(disposal_record, context={"request": request}).data,
                        message="Disposal record approved successfully"
                    )

                elif action == 'reject':
                    # Validate rejection reason
                    rejection_reason = request.data.get('rejection_reason', '').strip()
                    if not rejection_reason:
                        return CustomResponse.errors(
                            message="Rejection reason is required",
                            data={"rejection_reason": "This field is required."},
                            code=STATUS_CODES["VALIDATION_ERROR"]
                        )

                    if len(rejection_reason) < 10:
                        return CustomResponse.errors(
                            message="Rejection reason must be at least 10 characters",
                            data={"rejection_reason": "Minimum 10 characters required."},
                            code=STATUS_CODES["VALIDATION_ERROR"]
                        )

                    # Reject the disposal record
                    disposal_record.status = 'rejected'
                    disposal_record.rejected_by = request.user
                    disposal_record.rejection_reason = rejection_reason
                    disposal_record.decision_date = date.today()
                    disposal_record.updated_by = request.user
                    disposal_record.save()

                    # Create audit trail
                    create_audit_trail(
                        disposal_record=disposal_record,
                        action="Rejected",
                        user=request.user,
                        comments=f"Rejection reason: {rejection_reason}"
                    )

                    return CustomResponse.success(
                        data=DisposalRecordDetailSerializer(disposal_record, context={"request": request}).data,
                        message="Disposal record rejected successfully"
                    )

        except NotFound as e:
            return CustomResponse.errors(message=str(e))
        except Exception as e:
            return CustomResponse.server_error(
                message=f"Failed to {action} disposal record: {str(e)}"
            )


class DisposalResubmitView(APIView):
    """View for resubmitting a rejected disposal record"""
    permission_classes = [IsAuthenticated, HasMethodPermission]
    required_permissions = {
        "post": [
            "change_disposalrecord",
        ],
    }

    def _get_disposal_record(self, uid):
        disposal_record = DisposalRecord.objects.filter(uid=uid, is_deleted=False).first()
        if not disposal_record:
            raise NotFound("Disposal Record not found")
        return disposal_record

    def post(self, request, uid=None):
        """
        Resubmit a rejected disposal record for approval again.
        Requires a resubmission note explaining why it should be approved.
        Uses DisposalConversation and DisposalAuditTrail to track the resubmission.
        """
        try:
            if not uid:
                return CustomResponse.errors(message="Disposal Record UID is required")

            resubmission_note = request.data.get('resubmission_note', '').strip()
            if not resubmission_note:
                return CustomResponse.errors(
                    message="Resubmission note is required",
                    data={"resubmission_note": "Please explain why this disposal should be approved."},
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )

            if len(resubmission_note) < 20:
                return CustomResponse.errors(
                    message="Resubmission note must be at least 20 characters",
                    data={"resubmission_note": "Please provide a more detailed explanation (minimum 20 characters)."},
                    code=STATUS_CODES["VALIDATION_ERROR"]
                )

            with transaction.atomic():
                disposal_record = self._get_disposal_record(uid)

                # Only rejected records can be resubmitted
                if disposal_record.status != 'rejected':
                    return CustomResponse.errors(
                        message=f"Only rejected disposal records can be resubmitted. Current status: {disposal_record.status}"
                    )

                # Store previous rejection info for audit trail
                previous_rejection_reason = disposal_record.rejection_reason
                previous_rejected_by = disposal_record.rejected_by
                
                # Update the disposal record - reset to pending
                disposal_record.status = 'pending'
                disposal_record.decision_date = None  # Reset decision date
                disposal_record.rejected_by = None  # Clear rejected_by
                disposal_record.rejection_reason = None  # Clear rejection reason
                disposal_record.updated_by = request.user
                disposal_record.save()

                # Create audit trail entry for resubmission
                rejected_by_name = f"{previous_rejected_by.first_name} {previous_rejected_by.last_name}" if previous_rejected_by else "Unknown"
                create_audit_trail(
                    disposal_record=disposal_record,
                    action="Resubmitted",
                    user=request.user,
                    comments=f"Resubmitted after rejection by {rejected_by_name}.\nResubmission justification: {resubmission_note}\nPrevious rejection reason: {previous_rejection_reason}"
                )

                # Create a conversation entry for the resubmission (using 'clarification' type)
                DisposalConversation.objects.create(
                    disposal_record=disposal_record,
                    sender=request.user,
                    message=f"**Resubmission Request**\n\nThis disposal request has been resubmitted for approval.\n\n**Justification:**\n{resubmission_note}\n\n**Previous rejection reason:** {previous_rejection_reason}",
                    message_type='clarification',
                    created_by=request.user,
                    updated_by=request.user,
                )

                return CustomResponse.success(
                    data=DisposalRecordDetailSerializer(disposal_record, context={"request": request}).data,
                    message="Disposal record resubmitted successfully for approval"
                )

        except NotFound as e:
            return CustomResponse.errors(message=str(e))
        except Exception as e:
            return CustomResponse.server_error(
                message=f"Failed to resubmit disposal record: {str(e)}"
            )


class DisposalCancelView(APIView):
    """View for accepting rejection - keeps status as rejected, records in audit trail"""
    permission_classes = [IsAuthenticated, HasMethodPermission]
    required_permissions = {
        "post": [
            "change_disposalrecord",
        ],
    }

    def _get_disposal_record(self, uid):
        disposal_record = DisposalRecord.objects.filter(uid=uid, is_deleted=False).first()
        if not disposal_record:
            raise NotFound("Disposal Record not found")
        return disposal_record

    def post(self, request, uid=None):
        """
        Accept the rejection and close the disposal request.
        The asset will remain in service. Status stays as 'rejected'.
        Uses DisposalConversation and DisposalAuditTrail to track the acceptance.
        User can later edit/resubmit the rejected record if needed.
        """
        try:
            if not uid:
                return CustomResponse.errors(message="Disposal Record UID is required")

            cancellation_reason = request.data.get('cancellation_reason', '').strip()
            
            with transaction.atomic():
                disposal_record = self._get_disposal_record(uid)

                # Only rejected records can have rejection accepted
                if disposal_record.status != 'rejected':
                    return CustomResponse.errors(
                        message=f"Only rejected disposal records can have rejection accepted. Current status: {disposal_record.status}"
                    )

                # Keep status as 'rejected' - user can edit/resubmit later if needed
                disposal_record.updated_by = request.user
                disposal_record.save()

                # Create audit trail entry
                create_audit_trail(
                    disposal_record=disposal_record,
                    action="Rejection Accepted",
                    user=request.user,
                    comments=f"User accepted the rejection. Asset will remain in service.{f' Note: {cancellation_reason}' if cancellation_reason else ''}"
                )

                # Create a conversation entry for the acceptance (using 'decision' type)
                DisposalConversation.objects.create(
                    disposal_record=disposal_record,
                    sender=request.user,
                    message=f"**Rejection Accepted**\n\nThe rejection has been accepted. The asset will remain in active service.\n{f'Note: {cancellation_reason}' if cancellation_reason else 'No additional notes provided.'}",
                    message_type='decision',
                    created_by=request.user,
                    updated_by=request.user,
                )

                return CustomResponse.success(
                    data={"uid": str(disposal_record.uid), "status": "rejected"},
                    message="Rejection accepted. The asset will remain in service. You can edit and resubmit this record later if needed."
                )

        except NotFound as e:
            return CustomResponse.errors(message=str(e))
        except Exception as e:
            return CustomResponse.server_error(
                message=f"Failed to accept rejection: {str(e)}"
            )