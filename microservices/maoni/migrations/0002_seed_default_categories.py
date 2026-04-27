from django.db import migrations


def seed_categories(apps, schema_editor):
    MaoniCategory = apps.get_model("maoni", "MaoniCategory")
    if MaoniCategory.objects.exists():
        return
    defaults = ["General", "Facilities", "HR & Culture", "IT & Systems", "Safety"]
    for name in defaults:
        MaoniCategory.objects.create(name=name, is_active=True)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("maoni", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_categories, noop_reverse),
    ]
