from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("shipping", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="address",
            name="is_deleted",
            field=models.BooleanField(default=False, verbose_name="Diarsipkan"),
        ),
    ]
