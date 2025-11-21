from datetime import datetime

from django.db import transaction
from django.utils import timezone
from django.db.models import Q
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView

from microservices.oxygen_managements.models import OxygenReceiving, LocationOxygenVolumes, OxygenReceiveItem
from microservices.oxygen_managements.serializers import OxygenReceivingSerializer, OxygenReceivingVerifySerializer, \
    OxygenReceiveItemSerializer
from mnh_approval.pagination import CustomPagination
from mnh_approval.response_codes import CustomResponse, STATUS_CODES


class OxygenReceivingView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OxygenReceivingSerializer

    def get(self, request, uid=None):
        try:
            if uid:
                oxygen_receive = OxygenReceiving.objects.filter(uid=uid, is_deleted=False).prefetch_related('receive_items').first()
                if not oxygen_receive:
                    raise NotFound("Oxygen Receiving not found")
                return CustomResponse.success(data=OxygenReceivingSerializer(oxygen_receive).data)

            oxygen_receives = OxygenReceiving.objects.filter(is_deleted=False)


            search_query = request.GET.get('search', '').strip()
            # Path filters
            location_uid = request.GET.get('location', '').strip()
            status = request.GET.get('status', '').strip()
            date = request.GET.get('date', '').strip()

            if search_query:
                oxygen_receives = oxygen_receives.filter(
                    Q(quantity__icontains=search_query) |
                    Q(receiving_number__icontains=search_query)
                )

            # Apply path filters if provided
            if location_uid:
                oxygen_receives = oxygen_receives.filter(location__uid=location_uid)

            if status:
                oxygen_receives = oxygen_receives.filter(status=str(status).upper())

            if date:
                oxygen_receives = oxygen_receives.filter(date__date=date)  # Only compare date part

            if oxygen_receives.exists():
                return CustomPagination.paginate(view_class=self, results=oxygen_receives, request=request)

            return CustomResponse.errors(message="Oxygen Receiving not found", data=[])
        except Exception as e:
            print('Oxygen Receiving not found', e)
            return CustomResponse.server_error(message=f'Failed to Retrieve Oxygen Receiving: {str(e)}', )

    def post(self, request):
        try:
            with (transaction.atomic()):
                uid = request.data.get('uid', None)
                if uid:
                    try:
                        instance = OxygenReceiving.objects.get(uid=uid)
                        # avoid user to register verified receiving
                        if instance.status == "VERIFIED":
                            return CustomResponse.errors(
                                message="Readonly : The Receiving Data Already Verified",
                                code=STATUS_CODES['FORBIDDEN']
                            )
                        serializer = self.serializer_class(instance, data=request.data, partial=True)
                    except OxygenReceiving.DoesNotExist:
                        return CustomResponse.errors(message="Receiving Details not found")

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
            print(f'Failed to Retrieve Oxygen Receiving: {str(e)}')
            return CustomResponse.server_error(message=f'Failed to Change Oxygen Receiving: {str(e)}', )

    def delete(self, request, uid):
        try:
            with transaction.atomic():
                """ Soft delete a Oxygen Receiving by UID """
                oxygen_receive = OxygenReceiving.objects.filter(uid=uid, is_deleted=False).first()
                if not oxygen_receive:
                    return CustomResponse.errors(message="Oxygen Receiving Not Found or Deleted",)

                oxygen_receive.is_deleted = True
                oxygen_receive.deleted_at = datetime.now()
                oxygen_receive.deleted_by = request.user
                oxygen_receive.save()
                return CustomResponse.success(message='Oxygen Receiving deleted successfully')

        except Exception as e:
            return CustomResponse.server_error(message="Something went wrong While Deleting Oxygen Receiving")



class OxygenReceivingVerifyView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = OxygenReceivingVerifySerializer

    def post(self, request, uid):
        try:
            with (transaction.atomic()):
                oxygen_receiving = OxygenReceiving.objects.filter(uid=uid, is_deleted=False).first()
                if not oxygen_receiving:
                    return CustomResponse.errors(message="Oxygen Receiving Not Found or Deleted")

                if oxygen_receiving.status == 'VERIFIED':
                    return CustomResponse.errors(message="Oxygen Receiving Already Verified")

                # Validate and apply serializer
                serializer = self.serializer_class(oxygen_receiving, data=request.data, partial=True)
                if not serializer.is_valid():
                    return CustomResponse.errors(
                        message="Validation Error",
                        data=serializer.errors,
                        code=STATUS_CODES["VALIDATION_ERROR"]
                    )

                remarks = request.data.get('remarks','')
                item_uids = serializer.validated_data.get("item_uids")
                status = request.data.get('status','')

                if status not in ["VERIFIED", "REJECTED"]:
                    return CustomResponse.errors(message="Invalid status. Must be VERIFIED or REJECTED.")

                # Get items to verify or reject
                items = OxygenReceiveItem.objects.filter(
                    uid__in=item_uids,
                    receiving=oxygen_receiving,
                    is_deleted=False
                )

                if not items.exists():
                    return CustomResponse.errors(message="No valid items found for verification/rejection")

                # Update selected items
                now = timezone.now()
                user = request.user
                items.update(
                    status=status,
                    verify_date=now,
                    verify_by=user,
                    updated_by=user
                )

                # Determine the final status of receiving
                all_items = oxygen_receiving.receive_items.filter(is_deleted=False)
                total_items = all_items.count()
                verified_count = all_items.filter(status="VERIFIED").count()
                rejected_count = all_items.filter(status="REJECTED").count()

                if verified_count == total_items:
                    final_status = "VERIFIED"
                elif rejected_count == total_items:
                    final_status = "REJECTED"
                else:
                    final_status = "PARTIAL_VERIFIED"

                oxygen_receiving.status = final_status
                oxygen_receiving.remarks = remarks
                oxygen_receiving.save(update_fields=["status","remarks"])


                # Update related location quantity
                location = oxygen_receiving.location
                to_update = []
                to_create = []

                # Bulk update LocationOxygenVolumes based on verified items
                verified_items = items.filter(status="VERIFIED")

                for v_item in verified_items:
                    location_volumes = LocationOxygenVolumes.objects.filter(
                        location=oxygen_receiving.location,
                        volume=v_item.volume,
                        is_deleted=False
                    ).first()
                    if location_volumes:
                        location_volumes.quantity += v_item.quantity
                        location_volumes.updated_by = user
                        to_update.append(location_volumes)
                    else:
                        to_create.append(LocationOxygenVolumes(
                            location=oxygen_receiving.location,
                            volume=v_item.volume,
                            quantity=v_item.quantity,
                            created_at=now,
                            updated_at=now,
                            created_by=user,
                            updated_by=user
                        ))

                if to_create:
                    LocationOxygenVolumes.objects.bulk_create(to_create)

                if to_update:
                    LocationOxygenVolumes.objects.bulk_update(to_update, ["quantity", "updated_by", "updated_at"])

                location_volumes.update_location_quantity()


                return CustomResponse.success(message='Oxygen Receiving Verified successfully')

        except Exception as e:
            return CustomResponse.server_error(message=f'Failed to Change Oxygen Receiving: {str(e)}', )

class AddOxygenReceiveItemAPIView(APIView):
    def post(self, request, receiving_uid):
        try:
            receiving = OxygenReceiving.objects.get(uid=receiving_uid, is_deleted=False)
            if receiving.status == 'VERIFIED':
                return CustomResponse.errors(message="Receiving already verified")

            serializer = OxygenReceiveItemSerializer(data=request.data)
            if serializer.is_valid():
                validated = serializer.validated_data
                OxygenReceiveItem.objects.create(
                    receiving=receiving,
                    volume=validated['volume'],
                    supplier=validated['supplier'],
                    quantity=validated['quantity'],
                    created_by=request.user.id,
                    updated_by=request.user.id,
                )
                return CustomResponse.success(message="Item added successfully")
            return CustomResponse.errors(data=serializer.errors)

        except OxygenReceiving.DoesNotExist:
            return CustomResponse.errors(message="Receiving not found")
        except Exception as e:
            return CustomResponse.server_error(message=str(e))

class DeleteOxygenReceiveItemAPIView(APIView):
    def delete(self, request, item_uid):
        try:
            item = OxygenReceiveItem.objects.get(uid=item_uid, is_deleted=False)
            if item.receiving.status == 'VERIFIED':
                return CustomResponse.errors(message="Cannot delete from verified receiving")

            item.is_deleted = True
            item.updated_by = request.user.id
            item.save()
            return CustomResponse.success(message="Item deleted successfully")

        except OxygenReceiveItem.DoesNotExist:
            return CustomResponse.errors(message="Item not found")
        except Exception as e:
            return CustomResponse.server_error(message=str(e))
