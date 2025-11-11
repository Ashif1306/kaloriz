from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="PaymentMethod",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "name",
                    models.CharField(max_length=100, verbose_name="Nama Metode"),
                ),
                (
                    "slug",
                    models.SlugField(max_length=100, unique=True, verbose_name="Slug"),
                ),
                (
                    "tagline",
                    models.CharField(blank=True, max_length=150, verbose_name="Tagline"),
                ),
                (
                    "description",
                    models.TextField(blank=True, verbose_name="Deskripsi"),
                ),
                (
                    "additional_info",
                    models.TextField(blank=True, verbose_name="Informasi Tambahan"),
                ),
                (
                    "button_label",
                    models.CharField(
                        blank=True,
                        help_text="Kosongkan untuk menggunakan teks default 'Checkout'",
                        max_length=50,
                        verbose_name="Teks Tombol Checkout",
                    ),
                ),
                (
                    "logo",
                    models.ImageField(
                        blank=True,
                        help_text="Opsional, tampilkan logo di daftar metode pembayaran",
                        null=True,
                        upload_to="payment_methods/",
                        verbose_name="Logo",
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(default=True, verbose_name="Aktif"),
                ),
                (
                    "display_order",
                    models.PositiveIntegerField(
                        default=0,
                        help_text="Metode dengan angka lebih kecil akan tampil lebih dulu",
                        verbose_name="Urutan Tampil",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="Dibuat"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="Diperbarui"),
                ),
            ],
            options={
                "ordering": ["display_order", "name"],
                "verbose_name": "Metode Pembayaran",
                "verbose_name_plural": "Metode Pembayaran",
            },
        ),
    ]
