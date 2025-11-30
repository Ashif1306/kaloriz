from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

from .models import Notification, Order


@receiver(pre_save, sender=Order)
def store_previous_order_status(sender, instance, **kwargs):
    """Store the previous order status before saving so we can detect changes."""
    if not instance.pk:
        instance._previous_status = None
        return

    try:
        previous = sender.objects.get(pk=instance.pk)
        instance._previous_status = previous.status
    except sender.DoesNotExist:
        instance._previous_status = None


@receiver(post_save, sender=Order)
def create_notification_on_status_change(sender, instance, created, **kwargs):
    """Create a notification whenever an order status changes."""
    previous_status = getattr(instance, "_previous_status", None)

    if created:
        return

    if previous_status and previous_status != instance.status:
        Notification.objects.create(
            user=instance.user,
            title="Status Pesanan Diperbarui",
            message=f"Status pesanan {instance.order_number} berubah menjadi {instance.get_status_display()}",
        )
