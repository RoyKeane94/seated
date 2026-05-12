from django.db import migrations, models


def copy_address_to_line1(apps, schema_editor):
    Restaurant = apps.get_model("restaurants", "Restaurant")
    for r in Restaurant.objects.all():
        addr = (getattr(r, "address", None) or "").strip()
        if addr and not getattr(r, "address_line1", ""):
            r.address_line1 = addr[:255]
            r.save(update_fields=["address_line1"])


class Migration(migrations.Migration):

    dependencies = [
        ("restaurants", "0002_restaurant_timezone"),
    ]

    operations = [
        migrations.AddField(
            model_name="restaurant",
            name="address_line1",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="restaurant",
            name="postcode",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.RunPython(copy_address_to_line1, migrations.RunPython.noop),
        migrations.RemoveField(model_name="restaurant", name="address"),
        migrations.RemoveField(model_name="restaurant", name="cuisine"),
    ]
