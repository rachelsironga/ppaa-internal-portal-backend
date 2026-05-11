from django.core.management.base import BaseCommand
from django.db import transaction

from microservices.maoni.models import MaoniCategory


DEFAULT_CATEGORY_NAMES = [
    "Human Resources",
    "ICT",
    "Procurement",
    "Planning",
    "Finance",
    "Legal",
    "Administration",
    "Operations",
    "Other",
]


class Command(BaseCommand):
    help = "Seed default Maoni categories (idempotent)."

    def handle(self, *args, **options):
        existing = set(
            MaoniCategory.objects.all().values_list("name", flat=True)
        )
        to_create = [n for n in DEFAULT_CATEGORY_NAMES if n not in existing]
        if not to_create:
            self.stdout.write(self.style.NOTICE("Maoni categories already seeded."))
            return

        with transaction.atomic():
            for name in to_create:
                MaoniCategory.objects.create(name=name, is_active=True)

        self.stdout.write(
            self.style.SUCCESS(f"Seeded {len(to_create)} Maoni categories.")
        )

