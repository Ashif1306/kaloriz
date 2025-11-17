from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0008_order_midtrans_order_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="midtrans_token",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Token Snap terakhir yang diterbitkan untuk pesanan ini",
                max_length=255,
                verbose_name="Midtrans Snap Token",
            ),
        ),
    ]
