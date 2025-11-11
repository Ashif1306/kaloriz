from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0004_product_nutrition_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="carbohydrates",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Jumlah karbohidrat per porsi dalam gram (opsional)",
                max_digits=6,
                null=True,
                verbose_name="Karbohidrat (g)",
            ),
        ),
    ]
