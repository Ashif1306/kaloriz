from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0004_order_shipping_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="paymentmethod",
            name="service_status",
            field=models.CharField(
                choices=[("available", "Tersedia"), ("disrupted", "Sedang Gangguan")],
                default="available",
                help_text="Gunakan 'Sedang Gangguan' untuk menampilkan notifikasi masalah di halaman checkout.",
                max_length=20,
                verbose_name="Status Layanan",
            ),
        ),
    ]
