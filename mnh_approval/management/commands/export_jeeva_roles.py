import json
import os
from django.core.management.base import BaseCommand
from django.conf import settings

from api.serializers import JeevaRoleNestedSerializer
from mnh_model.models import JeevaRole


class Command(BaseCommand):
    help = "Export all Jeeva roles and permissions from the DB into a JSON file"

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            type=str,
            default='jeeva_roles_export.json',
            help='Output filename (default: jeeva_roles_export.json)'
        )

    def handle(self, *args, **options):
        output_filename = options['output']
        output_path = os.path.join(settings.BASE_DIR, output_filename)

        try:
            # Get all active roles
            roles_qs = JeevaRole.objects.filter(is_deleted=False, is_active=True).order_by("code")

            # Use serializer to build the structure
            serializer = JeevaRoleNestedSerializer(roles_qs, many=True)
            data = serializer.data

            # Wrap it in the required format
            output_data = {"Modules": data}

            # Write to file
            with open(output_path, "w", encoding="utf-8") as json_file:
                json.dump(output_data, json_file, indent=2, ensure_ascii=False)

            self.stdout.write(self.style.SUCCESS(f"✅ Exported {len(data)} roles to {output_path}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Failed to export roles: {e}"))
