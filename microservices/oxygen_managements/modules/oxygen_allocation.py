from datetime import datetime
from django.utils import timezone

from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView

from microservices.oxygen_managements.models import OxygenAllocation, OxygenAllocationItem, LocationOxygenVolumes
from microservices.oxygen_managements.serializers import OxygenAllocationSerializer, OxygenAllocationVerifySerializer
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES


class OxygenAllocationView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OxygenAllocationSerializer

    def get(self, request, uid=None):
        try:
            if uid:
                oxygen_allocation = OxygenAllocation.objects.filter(uid=uid, is_deleted=False).first()
                if not oxygen_allocation:
                    raise NotFound("Oxygen Allocation not found")
                return CustomResponse.success(data=OxygenAllocationSerializer(oxygen_allocation).data)

            search_query = request.GET.get('search', '').strip()
            # Path filters
            location_from_uid = request.GET.get('location_from','').strip()
            location_to_uid = request.GET.get('location_to','').strip()
            status = request.GET.get('status','').strip()
            date = request.GET.get('date','').strip()

            oxygen_allocations = OxygenAllocation.objects.filter(is_deleted=False)

            if search_query:
                oxygen_allocations = oxygen_allocations.filter(
                    Q(quantity__icontains=search_query) |
                    Q(location_from__name__icontains=search_query) |
                    Q(location_from__code__icontains=search_query) |
                    Q(location_to__name__icontains=search_query) |
                    Q(location_to__code__icontains=search_query) |
                    Q(date__date__icontains=search_query)
                )

            # Apply path filters if provided
            if location_from_uid:
                oxygen_allocations = oxygen_allocations.filter(location_from__uid=location_from_uid)

            if location_to_uid:
                oxygen_allocations = oxygen_allocations.filter(location_to__uid=location_to_uid)

            if status:
                if str(status).upper() != "ALL":
                    status_value =  str(status).upper().replace(" ", "_")
                    oxygen_allocations = oxygen_allocations.filter(status=status_value)

            if date:
                oxygen_allocations = oxygen_allocations.filter(date__date=date)  # Only compare date part

            if oxygen_allocations.exists():
                return CustomPagination.paginate(view_class=self, results=oxygen_allocations, request=request)

            return CustomResponse.errors(message="Oxygen Allocation not found", data=[])
        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Retrieve Oxygen Allocations: {str(e)}', )

    def post(self, request):
        try:
            with (transaction.atomic()):
                uid = request.data.get('uid', None)
                if uid:
                    try:
                        instance = OxygenAllocation.objects.get(uid=uid)
                        # avoid user to register verified allocation
                        if instance.status == "VERIFIED":
                            return CustomResponse.errors(
                                message="Readonly : The Allocation Data Already Verified",
                                code=STATUS_CODES['FORBIDDEN']
                            )
                        serializer = self.serializer_class(instance, data=request.data, partial=True)
                    except OxygenAllocation.DoesNotExist:
                        return CustomResponse.errors(message="Allocation Details not found")

                else:
                    serializer = self.serializer_class(data=request.data)

                if serializer.is_valid():
                    serializer.save(created_by=request.user, updated_by=request.user)
                    return CustomResponse.success(data=serializer.data)

                # Validation failed
                return CustomResponse.errors(
                    message="Validation Failed, Please Try Again",
                    data=serializer.errors,
                    code=STATUS_CODES["VALIDATION_ERROR"],
                )

        except Exception as e:
            print(f'Failed to Retrieve Oxygen Allocation: {str(e)}')
            return CustomResponse.server_error(message=f'Failed to Change Oxygen Allocation: {str(e)}', )

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                """ Soft delete a Oxygen Allocation by UID """
                oxygen_allocation = OxygenAllocation.objects.filter(uid=uid, is_deleted=False).first()
                if not oxygen_allocation:
                    return CustomResponse.errors(message="Oxygen Allocation Not Found or Deleted",)

                oxygen_allocation.is_deleted = True
                oxygen_allocation.deleted_at = datetime.now()
                oxygen_allocation.deleted_by = request.user
                oxygen_allocation.save()
                return CustomResponse.success(message='Oxygen Allocation deleted successfully')

        except Exception as e:
            return CustomResponse.server_error(message="Something went wrong While Deleting Oxygen Allocation")


class OxygenAllocationVerifyView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OxygenAllocationVerifySerializer

    def post(self, request, uid):
        try:
            with transaction.atomic():
                allocation = OxygenAllocation.objects.filter(uid=uid, is_deleted=False).first()
                if not allocation:
                    return CustomResponse.errors(message="Oxygen Allocation Not Found or Deleted")

                if allocation.status == 'VERIFIED':
                    return CustomResponse.errors(message="Oxygen Allocation Already Verified")

                serializer = self.serializer_class(allocation, data=request.data, partial=True)
                if not serializer.is_valid():
                    return CustomResponse.errors(
                        message="Validation Error",
                        data=serializer.errors,
                        code=STATUS_CODES["VALIDATION_ERROR"]
                    )

                remarks = request.data.get("remarks", "")
                status = request.data.get("status", "")
                item_uids = serializer.validated_data.get("item_uids")

                if status not in ["VERIFIED", "REJECTED"]:
                    return CustomResponse.errors(message="Invalid status. Must be VERIFIED or REJECTED.")

                items = OxygenAllocationItem.objects.filter(
                    uid__in=item_uids,
                    allocation=allocation,
                    is_deleted=False
                )
                if not items.exists():
                    return CustomResponse.errors(message="No valid items found for verification/rejection")

                now = timezone.now()
                user = request.user

                # Validate stock from source location
                if status == "VERIFIED":
                    for item in items:
                        from_volume = LocationOxygenVolumes.objects.filter(
                            location=allocation.location_from,
                            volume=item.volume,
                            is_deleted=False
                        ).first()
                        if not from_volume or from_volume.quantity < item.quantity:
                            return CustomResponse.errors(
                                message=f"Low Stock: {allocation.location_from.code} ({item.volume.volume}) has only {from_volume.quantity if from_volume else 0}, required {item.quantity}",
                                code=STATUS_CODES["PROCESS_FAILED"]
                            )

                # Update item verification
                items.update(
                    status=status,
                    verify_date=now,
                    verify_by=user,
                    updated_by=user
                )

                # Determine allocation status
                all_items = allocation.allocation_items.filter(is_deleted=False)
                verified = all_items.filter(status="VERIFIED").count()
                rejected = all_items.filter(status="REJECTED").count()
                total = all_items.count()

                if verified == total:
                    final_status = "VERIFIED"
                elif rejected == total:
                    final_status = "REJECTED"
                else:
                    final_status = "PARTIAL_VERIFIED"

                allocation.status = final_status
                allocation.remarks = remarks
                allocation.save(update_fields=["status", "remarks"])

                # Update stock only for VERIFIED items
                verified_items = items.filter(status="VERIFIED")
                to_create_from, to_update_from = [], []
                to_create_to, to_update_to = [], []

                for item in verified_items:
                    # Decrease from source
                    from_volume = LocationOxygenVolumes.objects.get(
                        location=allocation.location_from,
                        volume=item.volume,
                        is_deleted=False
                    )
                    from_volume.quantity -= item.quantity
                    from_volume.updated_by = user
                    to_update_from.append(from_volume)

                    # Increase to destination
                    to_volume = LocationOxygenVolumes.objects.filter(
                        location=allocation.location_to,
                        volume=item.volume,
                        is_deleted=False
                    ).first()

                    if to_volume:
                        to_volume.quantity += item.quantity
                        to_volume.updated_by = user
                        to_update_to.append(to_volume)
                    else:
                        to_create_to.append(LocationOxygenVolumes(
                            location=allocation.location_to,
                            volume=item.volume,
                            quantity=item.quantity,
                            created_by=user,
                            updated_by=user,
                            created_at=now,
                            updated_at=now
                        ))

                # Perform DB operations
                if to_update_from:
                    LocationOxygenVolumes.objects.bulk_update(to_update_from, ['quantity', 'updated_by', 'updated_at'])

                if to_update_to:
                    LocationOxygenVolumes.objects.bulk_update(to_update_to, ['quantity', 'updated_by', 'updated_at'])

                if to_create_to:
                    LocationOxygenVolumes.objects.bulk_create(to_create_to)

                # Refresh location quantities
                allocation.location_from.update_quantity()
                allocation.location_to.update_quantity()

                return CustomResponse.success(message="Oxygen Allocation Verified successfully")

        except Exception as e:
            return CustomResponse.server_error(message=f"Failed to Verify Allocation: {str(e)}")
