from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_paymentmethod"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="shipping_provider",
            field=models.CharField(
                blank=True,
                choices=[
                    ("JNE", "JNE"),
                    ("JNT", "J&T Express"),
                    ("SICEPAT", "SiCepat Ekspres"),
                    ("POS", "Pos Indonesia"),
                    ("TIKI", "TIKI"),
                    ("LION", "Lion Parcel"),
                    ("ANTERAJA", "Anteraja"),
                    ("SAPX", "SAPX Express"),
                    ("GOSEND", "Gosend"),
                    ("GRAB", "GrabExpress"),
                ],
                max_length=20,
                verbose_name="Kurir Pengiriman",
                help_text="Pilih kurir berdasarkan layanan pengiriman",
            ),
        ),
        migrations.AddField(
            model_name="order",
            name="tracking_number",
            field=models.CharField(
                blank=True,
                max_length=100,
                verbose_name="Nomor Resi",
                help_text="Masukkan nomor resi pengiriman",
            ),
        ),
    ]
