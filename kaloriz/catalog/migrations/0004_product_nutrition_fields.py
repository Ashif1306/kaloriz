from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0003_coupon_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="calories",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Total kalori per porsi (opsional)",
                null=True,
                verbose_name="Kalori (kcal)",
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="fiber",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Jumlah serat per porsi dalam gram (opsional)",
                max_digits=6,
                null=True,
                verbose_name="Serat (g)",
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="fat",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Jumlah lemak per porsi dalam gram (opsional)",
                max_digits=6,
                null=True,
                verbose_name="Lemak (g)",
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="protein",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Jumlah protein per porsi dalam gram (opsional)",
                max_digits=6,
                null=True,
                verbose_name="Protein (g)",
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="vitamins",
            field=models.CharField(
                blank=True,
                help_text="Daftar vitamin utama (opsional)",
                max_length=255,
                verbose_name="Vitamin",
            ),
        ),
    ]
