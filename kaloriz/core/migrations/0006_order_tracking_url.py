from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0005_paymentmethod_service_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="tracking_url",
            field=models.URLField(
                blank=True,
                help_text="Masukkan URL pelacakan dari kurir",
                verbose_name="Link Pelacakan",
            ),
        ),
    ]
