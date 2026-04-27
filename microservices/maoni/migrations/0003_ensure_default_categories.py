from django.db import migrations


DEFAULT_CATEGORY_NAMES = [
    "General",
    "Facilities",
    "HR & Culture",
    "IT & Systems",
    "Safety",
]


def ensure_active_categories(apps, schema_editor):
    """
    Ensure at least the default categories exist and are active.
    Covers: empty table, seed migration skipped, or all rows deactivated in admin.
    """
    MaoniCategory = apps.get_model("maoni", "MaoniCategory")
    if MaoniCategory.objects.filter(is_active=True).exists():
        return
    for name in DEFAULT_CATEGORY_NAMES:
        existing = MaoniCategory.objects.filter(name=name).first()
        if existing:
            if not existing.is_active:
                existing.is_active = True
                existing.save(update_fields=["is_active"])
        else:
            MaoniCategory.objects.create(name=name, is_active=True)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("maoni", "0002_seed_default_categories"),
    ]

    operations = [
        migrations.RunPython(ensure_active_categories, noop_reverse),
    ]
