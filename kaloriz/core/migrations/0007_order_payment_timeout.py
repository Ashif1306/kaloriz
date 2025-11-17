from django.db import migrations, models
from django.utils import timezone
import datetime


def set_initial_payment_deadline(apps, schema_editor):  # pylint: disable=unused-argument
    Order = apps.get_model('core', 'Order')
    for order in Order.objects.filter(payment_deadline__isnull=True):
        reference_time = order.created_at or timezone.now()
        order.payment_deadline = reference_time + datetime.timedelta(hours=1)
        order.save(update_fields=['payment_deadline'])


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0006_order_tracking_url"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="payment_method",
            field=models.CharField(blank=True, max_length=100, verbose_name="Metode Pembayaran"),
        ),
        migrations.AddField(
            model_name="order",
            name="payment_method_display",
            field=models.CharField(
                blank=True,
                help_text="Label yang ditampilkan kepada pengguna",
                max_length=150,
                verbose_name="Nama Metode Pembayaran",
            ),
        ),
        migrations.AddField(
            model_name="order",
            name="payment_deadline",
            field=models.DateTimeField(
                blank=True,
                help_text="Waktu terakhir pembayaran sebelum pesanan dibatalkan otomatis",
                null=True,
                verbose_name="Batas Pembayaran",
            ),
        ),
        migrations.RunPython(set_initial_payment_deadline, migrations.RunPython.noop),
    ]
