from django.conf import settings
from django.db import migrations, models


def _build_midtrans_order_id(order_pk: int, max_length: int) -> str:
    prefix = getattr(settings, "MIDTRANS_ORDER_ID_PREFIX", "KALORIZ")
    prefix = (prefix or "KALORIZ").strip()
    pk_str = str(order_pk)
    remaining = max_length - len(pk_str) - 1

    if remaining <= 0:
        return pk_str[-max_length:]

    trimmed_prefix = prefix[:remaining]
    candidate = f"{trimmed_prefix}-{pk_str}" if trimmed_prefix else pk_str[-max_length:]
    return candidate[:max_length]


def populate_midtrans_ids(apps, schema_editor):  # pylint: disable=unused-argument
    Order = apps.get_model("core", "Order")
    field = Order._meta.get_field("midtrans_order_id")
    max_length = field.max_length

    orders = Order.objects.filter(models.Q(midtrans_order_id="") | models.Q(midtrans_order_id__isnull=True))
    for order in orders.iterator():
        order.midtrans_order_id = _build_midtrans_order_id(order.pk, max_length)
        order.save(update_fields=["midtrans_order_id"])


def reverse_noop(apps, schema_editor):  # pylint: disable=unused-argument
    """No reverse operation required."""


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0007_order_payment_timeout"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="midtrans_order_id",
            field=models.CharField(
                blank=True,
                default="",
                help_text="ID unik yang digunakan untuk transaksi Midtrans",
                max_length=50,
                verbose_name="Midtrans Order ID",
            ),
        ),
        migrations.RunPython(populate_midtrans_ids, reverse_noop),
    ]
