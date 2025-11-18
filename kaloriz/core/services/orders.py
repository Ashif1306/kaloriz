"""Order creation and stock management helpers."""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable, Mapping

from django.db import transaction
from django.db.models import F
from django.utils import timezone
from datetime import timedelta

from core.models import Order, OrderItem
from shipping.models import Shipment


def create_order_from_checkout(
    *,
    user,
    cart,
    selected_items: Iterable,
    selected_quantities: Mapping[int, int],
    order_number: str,
    subtotal: Decimal,
    shipping_cost: Decimal,
    total: Decimal,
    shipping_full_name: str,
    shipping_email: str,
    shipping_phone: str,
    shipping_address_text: str,
    shipping_city: str,
    shipping_postal_code: str,
    courier_service: str,
    district_name: str,
    eta: str | None,
    notes: str = "",
    shipping_address_obj=None,
    shipping_service_name: str = "",
    payment_method_slug: str | None = None,
    payment_method_display: str = "",
) -> Order:
    """Create an order snapshot from the current checkout selection."""

    courier_service = (courier_service or "").upper()

    order = Order.objects.create(
        user=user,
        order_number=order_number,
        status="pending",
        full_name=shipping_full_name,
        email=shipping_email,
        phone=shipping_phone,
        address=shipping_address_text,
        city=shipping_city,
        postal_code=shipping_postal_code,
        shipping_address=shipping_address_obj,
        selected_courier=courier_service,
        selected_service_name=shipping_service_name,
        subtotal=subtotal,
        shipping_cost=shipping_cost,
        total=total,
        notes=notes,
        payment_method=payment_method_slug or "",
        payment_method_display=payment_method_display or (payment_method_slug or ""),
        payment_deadline=timezone.now() + timedelta(hours=Order.PAYMENT_TIMEOUT_HOURS),
    )

    Shipment.objects.create(
        order=order,
        full_name=shipping_full_name,
        phone=shipping_phone,
        street=shipping_address_text,
        district_name=district_name,
        postal_code=shipping_postal_code,
        service=courier_service,
        cost=shipping_cost,
        eta=eta or "",
    )

    for item in selected_items:
        quantity = int(selected_quantities.get(item.pk, getattr(item, "quantity", 0)) or 0)
        if quantity <= 0:
            continue

        product = getattr(item, "product", None)
        if product is None:
            continue

        unit_price = product.get_display_price()

        OrderItem.objects.create(
            order=order,
            product=product,
            product_name=product.name,
            product_price=unit_price,
            quantity=quantity,
            subtotal=unit_price * quantity,
        )

        product.stock = F("stock") - quantity
        product.save(update_fields=["stock"])

    cart.items.filter(is_selected=True).delete()

    return order


def restore_order_stock(order: Order) -> None:
    """Return reserved stock to inventory for a cancelled order."""

    order_items = order.items.select_related("product")
    for item in order_items:
        product = item.product
        if product is None:
            continue

        product.stock = F("stock") + item.quantity
        product.save(update_fields=["stock"])


def cancel_order_due_to_timeout(order: Order) -> bool:
    """Cancel pending orders whose payment deadline has passed."""

    if order.status != "pending":
        return False

    deadline = order.get_payment_deadline()
    if deadline is None or timezone.now() < deadline:
        return False

    with transaction.atomic():
        restore_order_stock(order)
        order.status = "cancelled"
        if order.payment_deadline is None:
            order.payment_deadline = deadline
        update_fields = ["status", "payment_deadline"]
        if order.midtrans_snap_token:
            order.midtrans_snap_token = None
            update_fields.append("midtrans_snap_token")
    order.save(update_fields=update_fields)

    return True
