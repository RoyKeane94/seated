from django.db import migrations, models


def forwards_publish_existing_subscribed(apps, schema_editor):
    Restaurant = apps.get_model("restaurants", "Restaurant")
    Restaurant.objects.filter(subscription_active=True).update(booking_link_published=True)


class Migration(migrations.Migration):

    dependencies = [
        ("restaurants", "0003_restaurant_address_line1_postcode_remove_cuisine_address"),
    ]

    operations = [
        migrations.AddField(
            model_name="restaurant",
            name="booking_link_published",
            field=models.BooleanField(
                default=False,
                help_text="When False, guests cannot book via the public URL even if billing is active.",
            ),
        ),
        migrations.RunPython(forwards_publish_existing_subscribed, migrations.RunPython.noop),
    ]
