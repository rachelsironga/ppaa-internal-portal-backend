# ict_assets/modules/reports.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Sum, Avg, Q, F
from django.db.models.functions import TruncMonth, TruncWeek
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
import csv
from django.http import HttpResponse

from microservices.ict_assets.models import (
    Asset, Computer, NetworkDevice, Peripheral, Software,
    SoftwareInstallation, MaintenanceRecord, SupportTicket,
    AssetCategory, AssetType, Location, Building, Warranty, DisposalRecord
)


class AssetReportsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        report_type = request.query_params.get('type', 'summary')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        category_id = request.query_params.get('category')
        status_filter = request.query_params.get('status')
        location_id = request.query_params.get('location')

        assets = Asset.objects.filter(is_active=True)

        if start_date:
            assets = assets.filter(created_at__gte=start_date)
        if end_date:
            assets = assets.filter(created_at__lte=end_date)
        if category_id:
            assets = assets.filter(asset_type__category__uid=category_id)
        if status_filter:
            assets = assets.filter(status=status_filter)
        if location_id:
            assets = assets.filter(location__uid=location_id)

        if report_type == 'summary':
            return self._get_summary_report(assets)
        elif report_type == 'by_status':
            return self._get_status_report(assets)
        elif report_type == 'by_condition':
            return self._get_condition_report(assets)
        elif report_type == 'by_category':
            return self._get_category_report(assets)
        elif report_type == 'by_location':
            return self._get_location_report(assets)
        elif report_type == 'by_type':
            return self._get_type_report(assets)
        elif report_type == 'depreciation':
            return self._get_depreciation_report(assets)
        elif report_type == 'warranty':
            return self._get_warranty_report(assets)
        elif report_type == 'acquisition':
            return self._get_acquisition_report(assets)
        elif report_type == 'inventory':
            return self._get_inventory_report(assets)
        else:
            return self._get_summary_report(assets)

    def _get_summary_report(self, assets):
        total_assets = assets.count()
        total_value = assets.aggregate(total=Sum('purchase_cost'))['total'] or Decimal('0')
        avg_cost = assets.aggregate(avg=Avg('purchase_cost'))['avg'] or Decimal('0')

        status_breakdown = list(assets.values('status').annotate(
            count=Count('uid'),
            value=Sum('purchase_cost')
        ).order_by('-count'))

        category_breakdown = list(assets.values(
            category_name=F('asset_type__category__name')
        ).annotate(
            count=Count('uid'),
            value=Sum('purchase_cost')
        ).order_by('-count')[:10])

        today = timezone.now().date()
        thirty_days = today + timedelta(days=30)

        # Get condition distribution for each asset type
        computers_by_condition = list(Computer.objects.values(
            condition=F('asset__condition')
        ).annotate(count=Count('uid')).order_by('-count'))

        network_devices_by_condition = list(NetworkDevice.objects.values(
            condition=F('asset__condition')
        ).annotate(count=Count('uid')).order_by('-count'))

        peripherals_by_condition = list(Peripheral.objects.values(
            condition=F('asset__condition')
        ).annotate(count=Count('uid')).order_by('-count'))

        return Response({
            'report_type': 'summary',
            'generated_at': timezone.now().isoformat(),
            'summary': {
                'total_assets': total_assets,
                'total_value': float(total_value),
                'average_cost': float(avg_cost),
                'computers': Computer.objects.count(),
                'network_devices': NetworkDevice.objects.count(),
                'peripherals': Peripheral.objects.count(),
            },
            'asset_type_conditions': {
                'computers': computers_by_condition,
                'network_devices': network_devices_by_condition,
                'peripherals': peripherals_by_condition,
            },
            'status_breakdown': status_breakdown,
            'category_breakdown': category_breakdown,
            'warranty_expiring_30_days': assets.filter(
                warranty_expiry__gte=today,
                warranty_expiry__lte=thirty_days
            ).count(),
            'warranty_expired': assets.filter(warranty_expiry__lt=today).count(),
        })

    def _get_status_report(self, assets):
        status_data = list(assets.values('status').annotate(
            count=Count('uid'),
            total_value=Sum('purchase_cost'),
            avg_value=Avg('purchase_cost')
        ).order_by('-count'))

        return Response({
            'report_type': 'by_status',
            'generated_at': timezone.now().isoformat(),
            'data': status_data,
            'total_assets': assets.count()
        })

    def _get_condition_report(self, assets):
        condition_data = list(assets.values('condition').annotate(
            count=Count('uid'),
            total_value=Sum('purchase_cost'),
            avg_value=Avg('purchase_cost')
        ).order_by('-count'))

        return Response({
            'report_type': 'by_condition',
            'generated_at': timezone.now().isoformat(),
            'data': condition_data,
            'total_assets': assets.count()
        })

    def _get_category_report(self, assets):
        category_data = list(assets.values(
            category_uid=F('asset_type__category__uid'),
            category_name=F('asset_type__category__name')
        ).annotate(
            count=Count('uid'),
            total_value=Sum('purchase_cost'),
            avg_value=Avg('purchase_cost'),
            operational=Count('uid', filter=Q(status='operational')),
            in_repair=Count('uid', filter=Q(status='in_repair')),
        ).order_by('-count'))

        return Response({
            'report_type': 'by_category',
            'generated_at': timezone.now().isoformat(),
            'data': category_data,
            'total_assets': assets.count()
        })

    def _get_location_report(self, assets):
        location_data = list(assets.values(
            location_uid=F('location__uid'),
            location_name=F('location__name'),
            building_name=F('location__building__name')
        ).annotate(
            count=Count('uid'),
            total_value=Sum('purchase_cost'),
            operational=Count('uid', filter=Q(status='operational')),
        ).order_by('-count'))

        return Response({
            'report_type': 'by_location',
            'generated_at': timezone.now().isoformat(),
            'data': location_data,
            'total_assets': assets.count()
        })

    def _get_type_report(self, assets):
        type_data = list(assets.values(
            type_uid=F('asset_type__uid'),
            type_name=F('asset_type__name'),
            category_name=F('asset_type__category__name')
        ).annotate(
            count=Count('uid'),
            total_value=Sum('purchase_cost'),
            avg_value=Avg('purchase_cost'),
        ).order_by('-count'))

        return Response({
            'report_type': 'by_type',
            'generated_at': timezone.now().isoformat(),
            'data': type_data,
            'total_assets': assets.count()
        })

    def _get_depreciation_report(self, assets):
        depreciation_data = []
        for asset in assets.select_related('asset_type__category'):
            if asset.purchase_cost and asset.purchase_date:
                years_old = (timezone.now().date() - asset.purchase_date).days / 365
                useful_life = 5
                annual_depreciation = float(asset.purchase_cost) / useful_life
                accumulated = min(annual_depreciation * years_old, float(asset.purchase_cost))
                current_value = max(float(asset.purchase_cost) - accumulated, 0)

                depreciation_data.append({
                    'asset_tag': asset.asset_tag,
                    'purchase_cost': float(asset.purchase_cost),
                    'purchase_date': asset.purchase_date.isoformat() if asset.purchase_date else None,
                    'years_old': round(years_old, 2),
                    'accumulated_depreciation': round(accumulated, 2),
                    'current_value': round(current_value, 2),
                    'depreciation_rate': round((accumulated / float(asset.purchase_cost)) * 100, 2) if asset.purchase_cost else 0
                })

        return Response({
            'report_type': 'depreciation',
            'generated_at': timezone.now().isoformat(),
            'data': depreciation_data[:100],
            'total_original_value': sum(d['purchase_cost'] for d in depreciation_data),
            'total_current_value': sum(d['current_value'] for d in depreciation_data),
            'total_depreciation': sum(d['accumulated_depreciation'] for d in depreciation_data),
        })

    def _get_warranty_report(self, assets):
        today = timezone.now().date()
        thirty_days = today + timedelta(days=30)
        ninety_days = today + timedelta(days=90)

        warranty_data = {
            'active': assets.filter(warranty_expiry__gt=ninety_days).count(),
            'expiring_30_days': assets.filter(
                warranty_expiry__gte=today,
                warranty_expiry__lte=thirty_days
            ).count(),
            'expiring_90_days': assets.filter(
                warranty_expiry__gt=thirty_days,
                warranty_expiry__lte=ninety_days
            ).count(),
            'expired': assets.filter(warranty_expiry__lt=today).count(),
            'no_warranty': assets.filter(warranty_expiry__isnull=True).count(),
        }

        expiring_soon = list(assets.filter(
            warranty_expiry__gte=today,
            warranty_expiry__lte=ninety_days
        ).values(
            'uid', 'asset_tag', 'warranty_expiry', 'model',
            location_name=F('location__name')
        ).order_by('warranty_expiry')[:20])

        return Response({
            'report_type': 'warranty',
            'generated_at': timezone.now().isoformat(),
            'summary': warranty_data,
            'expiring_soon': expiring_soon,
            'total_assets': assets.count()
        })

    def _get_acquisition_report(self, assets):
        monthly_data = list(assets.filter(
            purchase_date__isnull=False
        ).annotate(
            month=TruncMonth('purchase_date')
        ).values('month').annotate(
            count=Count('uid'),
            total_value=Sum('purchase_cost')
        ).order_by('-month')[:12])

        return Response({
            'report_type': 'acquisition',
            'generated_at': timezone.now().isoformat(),
            'monthly_data': monthly_data,
            'total_assets': assets.count()
        })

    def _get_inventory_report(self, assets):
        inventory_data = list(assets.select_related(
            'asset_type', 'asset_type__category', 'location', 'custodian', 'manufacturer'
        ).values(
            'uid', 'asset_tag', 'serial_number', 'status', 'condition',
            'purchase_date', 'purchase_cost', 'warranty_expiry',
            type_name=F('asset_type__name'),
            category_name=F('asset_type__category__name'),
            location_name=F('location__name'),
            custodian_first=F('custodian__first_name'),
            custodian_last=F('custodian__last_name'),
            manufacturer_name=F('manufacturer__name'),
        )[:500])

        return Response({
            'report_type': 'inventory',
            'generated_at': timezone.now().isoformat(),
            'data': inventory_data,
            'total_count': assets.count()
        })


class MaintenanceReportsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        report_type = request.query_params.get('type', 'summary')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        status_filter = request.query_params.get('status')
        technician_id = request.query_params.get('technician')

        records = MaintenanceRecord.objects.all()

        if start_date:
            records = records.filter(scheduled_date__gte=start_date)
        if end_date:
            records = records.filter(scheduled_date__lte=end_date)
        if status_filter:
            records = records.filter(status=status_filter)
        if technician_id:
            records = records.filter(technician__uid=technician_id)

        if report_type == 'summary':
            return self._get_summary_report(records)
        elif report_type == 'by_status':
            return self._get_status_report(records)
        elif report_type == 'by_type':
            return self._get_type_report(records)
        elif report_type == 'by_technician':
            return self._get_technician_report(records)
        elif report_type == 'by_asset':
            return self._get_asset_report(records)
        elif report_type == 'cost_analysis':
            return self._get_cost_report(records)
        elif report_type == 'performance':
            return self._get_performance_report(records)
        else:
            return self._get_summary_report(records)

    def _get_summary_report(self, records):
        total_records = records.count()
        total_cost = records.aggregate(total=Sum('cost'))['total'] or Decimal('0')
        avg_cost = records.aggregate(avg=Avg('cost'))['avg'] or Decimal('0')

        status_breakdown = list(records.values('status').annotate(
            count=Count('uid'),
            total_cost=Sum('cost')
        ).order_by('-count'))

        type_breakdown = list(records.values('maintenance_type').annotate(
            count=Count('uid'),
            total_cost=Sum('cost')
        ).order_by('-count'))

        today = timezone.now().date()
        overdue = records.filter(
            status__in=['scheduled', 'in_progress'],
            scheduled_date__lt=today
        ).count()

        return Response({
            'report_type': 'summary',
            'generated_at': timezone.now().isoformat(),
            'summary': {
                'total_records': total_records,
                'total_cost': float(total_cost),
                'average_cost': float(avg_cost),
                'completed': records.filter(status='completed').count(),
                'in_progress': records.filter(status='in_progress').count(),
                'scheduled': records.filter(status='scheduled').count(),
                'overdue': overdue,
            },
            'status_breakdown': status_breakdown,
            'type_breakdown': type_breakdown,
        })

    def _get_status_report(self, records):
        status_data = list(records.values('status').annotate(
            count=Count('uid'),
            total_cost=Sum('cost'),
            avg_cost=Avg('cost')
        ).order_by('-count'))

        return Response({
            'report_type': 'by_status',
            'generated_at': timezone.now().isoformat(),
            'data': status_data,
            'total_records': records.count()
        })

    def _get_type_report(self, records):
        type_data = list(records.values('maintenance_type').annotate(
            count=Count('uid'),
            total_cost=Sum('cost'),
            avg_cost=Avg('cost'),
            completed=Count('uid', filter=Q(status='completed'))
        ).order_by('-count'))

        return Response({
            'report_type': 'by_type',
            'generated_at': timezone.now().isoformat(),
            'data': type_data,
            'total_records': records.count()
        })

    def _get_technician_report(self, records):
        technician_data = list(records.values(
            technician_guid=F('technician__guid'),
            technician_first=F('technician__first_name'),
            technician_last=F('technician__last_name')
        ).annotate(
            count=Count('uid'),
            total_cost=Sum('cost'),
            completed=Count('uid', filter=Q(status='completed')),
            in_progress=Count('uid', filter=Q(status='in_progress'))
        ).order_by('-count'))

        # Format the data for better display
        formatted_data = []
        for item in technician_data:
            first_name = item.get('technician_first') or ''
            last_name = item.get('technician_last') or ''
            technician_name = f"{first_name} {last_name}".strip() or 'Unassigned'
            formatted_data.append({
                'technician_guid': str(item.get('technician_guid')) if item.get('technician_guid') else None,
                'technician_name': technician_name,
                'count': item.get('count', 0),
                'total_cost': float(item.get('total_cost') or 0),
                'completed': item.get('completed', 0),
                'in_progress': item.get('in_progress', 0),
            })

        return Response({
            'report_type': 'by_technician',
            'generated_at': timezone.now().isoformat(),
            'data': formatted_data,
            'total_records': records.count()
        })

    def _get_asset_report(self, records):
        asset_data = list(records.values(
            asset_uid=F('asset__uid'),
            asset_tag=F('asset__asset_tag')
        ).annotate(
            maintenance_count=Count('uid'),
            total_cost=Sum('cost')
        ).order_by('-maintenance_count')[:50])

        return Response({
            'report_type': 'by_asset',
            'generated_at': timezone.now().isoformat(),
            'data': asset_data,
            'total_records': records.count()
        })

    def _get_cost_report(self, records):
        monthly_cost = list(records.filter(
            completed_date__isnull=False
        ).annotate(
            month=TruncMonth('completed_date')
        ).values('month').annotate(
            count=Count('uid'),
            total_cost=Sum('cost'),
            avg_cost=Avg('cost')
        ).order_by('-month')[:12])

        type_cost = list(records.values('maintenance_type').annotate(
            total_cost=Sum('cost'),
            avg_cost=Avg('cost'),
            count=Count('uid')
        ).order_by('-total_cost'))

        return Response({
            'report_type': 'cost_analysis',
            'generated_at': timezone.now().isoformat(),
            'monthly_cost': monthly_cost,
            'type_cost': type_cost,
            'total_cost': float(records.aggregate(total=Sum('cost'))['total'] or 0)
        })

    def _get_performance_report(self, records):
        completed = records.filter(
            status='completed',
            scheduled_date__isnull=False,
            completed_date__isnull=False
        )

        on_time = 0
        late = 0
        total_days = 0

        for record in completed:
            days_diff = (record.completed_date - record.scheduled_date).days
            total_days += abs(days_diff)
            if days_diff <= 0:
                on_time += 1
            else:
                late += 1

        completion_rate = (completed.count() / records.count() * 100) if records.count() > 0 else 0
        on_time_rate = (on_time / completed.count() * 100) if completed.count() > 0 else 0
        avg_completion_days = total_days / completed.count() if completed.count() > 0 else 0

        return Response({
            'report_type': 'performance',
            'generated_at': timezone.now().isoformat(),
            'metrics': {
                'completion_rate': round(completion_rate, 2),
                'on_time_rate': round(on_time_rate, 2),
                'average_completion_days': round(avg_completion_days, 2),
                'on_time_count': on_time,
                'late_count': late,
                'total_completed': completed.count(),
                'total_records': records.count()
            }
        })


class SoftwareReportsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        report_type = request.query_params.get('type', 'summary')
        category_id = request.query_params.get('category')
        license_type = request.query_params.get('license_type')

        software = Software.objects.all()

        if category_id:
            software = software.filter(category__uid=category_id)
        if license_type:
            software = software.filter(license_type=license_type)

        if report_type == 'summary':
            return self._get_summary_report(software)
        elif report_type == 'license':
            return self._get_license_report(software)
        elif report_type == 'installation':
            return self._get_installation_report()
        elif report_type == 'compliance':
            return self._get_compliance_report(software)
        elif report_type == 'expiring':
            return self._get_expiring_report(software)
        else:
            return self._get_summary_report(software)

    def _get_summary_report(self, software):
        total_software = software.count()
        total_licenses = software.aggregate(total=Sum('total_licenses'))['total'] or 0
        used_licenses = software.aggregate(total=Sum('used_licenses'))['total'] or 0
        total_cost = software.aggregate(total=Sum('purchase_cost'))['total'] or Decimal('0')

        license_breakdown = list(software.values('license_type').annotate(
            count=Count('uid'),
            total_licenses=Sum('total_licenses'),
            used_licenses=Sum('used_licenses')
        ).order_by('-count'))

        type_breakdown = list(software.values('software_type').annotate(
            count=Count('uid'),
            total_cost=Sum('purchase_cost')
        ).order_by('-count'))

        today = timezone.now().date()
        thirty_days = today + timedelta(days=30)

        return Response({
            'report_type': 'summary',
            'generated_at': timezone.now().isoformat(),
            'summary': {
                'total_software': total_software,
                'total_licenses': total_licenses,
                'used_licenses': used_licenses,
                'available_licenses': total_licenses - used_licenses,
                'license_utilization': round((used_licenses / total_licenses * 100), 2) if total_licenses > 0 else 0,
                'total_cost': float(total_cost),
                'expiring_30_days': software.filter(
                    license_expiry__gte=today,
                    license_expiry__lte=thirty_days
                ).count(),
            },
            'license_breakdown': license_breakdown,
            'type_breakdown': type_breakdown,
        })

    def _get_license_report(self, software):
        license_data = list(software.values(
            'uid', 'asset_tag', 'software_name', 'version', 'publisher',
            'license_type', 'total_licenses', 'used_licenses', 'license_expiry',
            'purchase_cost'
        ).order_by('software_name'))

        for item in license_data:
            item['available_licenses'] = item['total_licenses'] - item['used_licenses']
            item['utilization'] = round(
                (item['used_licenses'] / item['total_licenses'] * 100), 2
            ) if item['total_licenses'] > 0 else 0

        return Response({
            'report_type': 'license',
            'generated_at': timezone.now().isoformat(),
            'data': license_data,
            'total_count': software.count()
        })

    def _get_installation_report(self):
        installations = SoftwareInstallation.objects.select_related('software', 'asset')

        installation_data = list(installations.values(
            software_name=F('software__software_name'),
            software_version=F('software__version')
        ).annotate(
            installation_count=Count('uid'),
            active_count=Count('uid', filter=Q(status='active')),
            inactive_count=Count('uid', filter=Q(status='inactive'))
        ).order_by('-installation_count')[:50])

        return Response({
            'report_type': 'installation',
            'generated_at': timezone.now().isoformat(),
            'data': installation_data,
            'total_installations': installations.count()
        })

    def _get_compliance_report(self, software):
        compliance_data = []

        for sw in software:
            if sw.total_licenses > 0:
                status = 'compliant'
                if sw.used_licenses > sw.total_licenses:
                    status = 'over_licensed'
                elif sw.used_licenses == 0:
                    status = 'unused'

                compliance_data.append({
                    'uid': str(sw.uid),
                    'software_name': sw.software_name,
                    'version': sw.version,
                    'total_licenses': sw.total_licenses,
                    'used_licenses': sw.used_licenses,
                    'compliance_status': status,
                    'license_type': sw.license_type,
                })

        compliant = len([d for d in compliance_data if d['compliance_status'] == 'compliant'])
        over_licensed = len([d for d in compliance_data if d['compliance_status'] == 'over_licensed'])
        unused = len([d for d in compliance_data if d['compliance_status'] == 'unused'])

        return Response({
            'report_type': 'compliance',
            'generated_at': timezone.now().isoformat(),
            'summary': {
                'compliant': compliant,
                'over_licensed': over_licensed,
                'unused': unused,
                'compliance_rate': round((compliant / len(compliance_data) * 100), 2) if compliance_data else 0
            },
            'data': compliance_data[:100]
        })

    def _get_expiring_report(self, software):
        today = timezone.now().date()
        thirty_days = today + timedelta(days=30)
        ninety_days = today + timedelta(days=90)

        expiring_data = {
            'expired': list(software.filter(
                license_expiry__lt=today
            ).values('uid', 'software_name', 'version', 'license_expiry', 'total_licenses')[:20]),
            'expiring_30_days': list(software.filter(
                license_expiry__gte=today,
                license_expiry__lte=thirty_days
            ).values('uid', 'software_name', 'version', 'license_expiry', 'total_licenses')[:20]),
            'expiring_90_days': list(software.filter(
                license_expiry__gt=thirty_days,
                license_expiry__lte=ninety_days
            ).values('uid', 'software_name', 'version', 'license_expiry', 'total_licenses')[:20]),
        }

        return Response({
            'report_type': 'expiring',
            'generated_at': timezone.now().isoformat(),
            'summary': {
                'expired_count': software.filter(license_expiry__lt=today).count(),
                'expiring_30_days_count': software.filter(
                    license_expiry__gte=today,
                    license_expiry__lte=thirty_days
                ).count(),
                'expiring_90_days_count': software.filter(
                    license_expiry__gt=thirty_days,
                    license_expiry__lte=ninety_days
                ).count(),
            },
            'data': expiring_data
        })


class ExportDataAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        export_type = request.query_params.get('type', 'assets')
        format_type = request.query_params.get('format', 'json')

        if export_type == 'assets':
            data = self._get_assets_export()
        elif export_type == 'computers':
            data = self._get_computers_export()
        elif export_type == 'network_devices':
            data = self._get_network_devices_export()
        elif export_type == 'peripherals':
            data = self._get_peripherals_export()
        elif export_type == 'software':
            data = self._get_software_export()
        elif export_type == 'maintenance':
            data = self._get_maintenance_export()
        elif export_type == 'locations':
            data = self._get_locations_export()
        else:
            data = self._get_assets_export()

        if format_type == 'csv':
            return self._export_csv(data, export_type)
        else:
            return Response({
                'export_type': export_type,
                'generated_at': timezone.now().isoformat(),
                'count': len(data),
                'data': data
            })

    def _get_assets_export(self):
        return list(Asset.objects.select_related(
            'asset_type', 'asset_type__category', 'location', 'custodian', 'manufacturer', 'supplier'
        ).values(
            'uid', 'asset_tag', 'serial_number', 'barcode', 'model', 'status', 'condition',
            'purchase_date', 'purchase_cost', 'warranty_expiry', 'notes', 'created_at',
            type_name=F('asset_type__name'),
            category_name=F('asset_type__category__name'),
            location_name=F('location__name'),
            custodian_first=F('custodian__first_name'),
            custodian_last=F('custodian__last_name'),
            manufacturer_name=F('manufacturer__name'),
            supplier_name=F('supplier__name'),
        ))

    def _get_computers_export(self):
        return list(Computer.objects.select_related('asset').values(
            'uid', 'hostname', 'processor', 'cpu_cores', 'cpu_speed_ghz', 'ram_gb',
            'storage_type', 'storage_gb', 'operating_system', 'os_version',
            'mac_addresses', 'ip_addresses', 'gpu', 'virtual',
            asset_tag=F('asset__asset_tag'),
            serial_number=F('asset__serial_number'),
            status=F('asset__status'),
            location=F('asset__location__name'),
        ))

    def _get_network_devices_export(self):
        return list(NetworkDevice.objects.select_related('asset').values(
            'uid', 'device_type', 'ip_address', 'mac_address', 'ports',
            asset_tag=F('asset__asset_tag'),
            serial_number=F('asset__serial_number'),
            status=F('asset__status'),
            location=F('asset__location__name'),
        ))

    def _get_peripherals_export(self):
        return list(Peripheral.objects.select_related('asset').values(
            'uid', 'peripheral_type', 'connection_type',
            asset_tag=F('asset__asset_tag'),
            serial_number=F('asset__serial_number'),
            status=F('asset__status'),
            location=F('asset__location__name'),
        ))

    def _get_software_export(self):
        return list(Software.objects.values(
            'uid', 'asset_tag', 'software_name', 'version', 'publisher',
            'software_type', 'license_type', 'total_licenses', 'used_licenses',
            'license_expiry', 'purchase_cost', 'status',
            category_name=F('category__name'),
        ))

    def _get_maintenance_export(self):
        return list(MaintenanceRecord.objects.select_related('asset', 'technician').values(
            'uid', 'maintenance_type', 'status', 'scheduled_date', 'completed_date',
            'cost', 'description', 'notes',
            asset_tag=F('asset__asset_tag'),
            technician_first=F('technician__first_name'),
            technician_last=F('technician__last_name'),
        ))

    def _get_locations_export(self):
        return list(Location.objects.select_related('building', 'floor').values(
            'uid', 'name', 'code', 'room', 'address', 'description',
            building_name=F('building__name'),
            floor_number=F('floor__floor_number'),
        ))

    def _export_csv(self, data, export_type):
        if not data:
            return Response({'error': 'No data to export'}, status=status.HTTP_404_NOT_FOUND)

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{export_type}_export.csv"'

        writer = csv.DictWriter(response, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)

        return response
