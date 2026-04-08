from django.core.management.base import BaseCommand

from microservices.ppaa_maoni.models import MaoniCategory


class Command(BaseCommand):
    help = "Seed default Maoni Categories (Areas of Concern) into maoni_db."
    
    def add_arguments(self, parser):
        parser.add_argument(
            "--database",
            default="maoni",
            help="Database alias to use (default: maoni).",
        )

    DEFAULT_CATEGORIES = [
        # name, type, color, icon, order, is_public
        ("HR", "DEPARTMENTAL", "#dc2626", "fa-users", 10, True),
        ("ICT", "DEPARTMENTAL", "#2563eb", "fa-laptop", 20, True),
        ("Finance", "DEPARTMENTAL", "#16a34a", "fa-coins", 30, True),
        ("Procurement", "DEPARTMENTAL", "#f59e0b", "fa-cart-shopping", 40, True),
        ("Operations", "OPERATIONAL", "#7c3aed", "fa-gear", 50, True),
        ("General", "GENERAL", "#4f46e5", "fa-lightbulb", 60, True),
        ("Strategic", "STRATEGIC", "#0f766e", "fa-bullseye", 70, True),
    ]

    def handle(self, *args, **options):
        using = options.get("database") or "maoni"
        created = 0
        updated = 0

        for name, cat_type, color, icon, order, is_public in self.DEFAULT_CATEGORIES:
            obj, was_created = MaoniCategory.objects.using(using).get_or_create(
                name=name,
                defaults={
                    "type": cat_type,
                    "color": color,
                    "icon": icon,
                    "order": order,
                    "is_public": is_public,
                    "is_active": True,
                },
            )
            if was_created:
                created += 1
                continue

            # Keep existing records but ensure key fields are populated
            changed = False
            for field, value in {
                "type": cat_type,
                "color": color,
                "icon": icon,
                "order": order,
                "is_public": is_public,
                "is_active": True,
            }.items():
                if getattr(obj, field, None) in (None, "", 0, False) and value not in (None, "", 0, False):
                    setattr(obj, field, value)
                    changed = True

            if changed:
                obj.save(using=using)
                updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"MaoniCategory seed complete on db='{using}'. created={created}, updated={updated}"
        ))

