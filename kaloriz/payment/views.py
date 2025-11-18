"""Views for handling payment integrations."""
import base64
import datetime
import json
import logging
import uuid
import hashlib
import hmac
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from catalog.models import DiscountCode
from core.models import Order, PaymentMethod
from core.views import _get_active_cart, _prepare_selected_cart_items
from core.services.orders import create_order_from_checkout, restore_order_stock, cancel_order_due_to_timeout
from payment.services import get_or_create_midtrans_snap_token
from shipping.models import Address

logger = logging.getLogger(__name__)

try:  # pragma: no cover - defensive import check
    import midtransclient
except ImportError:  # pragma: no cover - handled at runtime
    midtransclient = None


def _get_doku_base_url() -> str:
    if getattr(settings, "DOKU_IS_PRODUCTION", False):
        return getattr(settings, "DOKU_PRODUCTION_BASE_URL", "https://api.doku.com")
    return getattr(settings, "DOKU_SANDBOX_BASE_URL", "https://api-sandbox.doku.com")


def _get_doku_config() -> dict:
    return {
        "client_id": getattr(settings, "DOKU_CLIENT_ID", ""),
        "secret_key": getattr(settings, "DOKU_SECRET_KEY", ""),
        "merchant_code": getattr(settings, "DOKU_MERCHANT_CODE", ""),
    }


def _format_iso_timestamp(dt) -> str:
    if dt.tzinfo is None:
        dt = timezone.make_aware(dt, timezone=datetime.timezone.utc)
    dt = dt.astimezone(datetime.timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _compute_doku_signature(
    target: str,
    *,
    client_id: str,
    secret_key: str,
    request_id: str,
    timestamp: str,
    digest_header_value: str,
) -> str:
    lines = [
        f"Client-Id: {client_id}",
        f"Request-Id: {request_id}",
        f"Request-Timestamp: {timestamp}",
        f"Request-Target: {target}",
        f"Digest: {digest_header_value}",
    ]
    string_to_sign = "\n".join(lines)
    signature = base64.b64encode(
        hmac.new(secret_key.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha256).digest()
    ).decode("utf-8")
    return f"HMACSHA256={signature}"


def _call_doku_api(target: str, payload: dict) -> tuple[int, dict, dict]:
    config = _get_doku_config()
    client_id = config.get("client_id")
    secret_key = config.get("secret_key")

    if not client_id or not secret_key:
        raise RuntimeError("Konfigurasi DOKU belum lengkap.")

    normalized_target = "/" + target.lstrip("/")
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    body_bytes = body.encode("utf-8")
    digest_raw = hashlib.sha256(body_bytes).digest()
    digest_value = base64.b64encode(digest_raw).decode("utf-8")

    base_url = _get_doku_base_url().rstrip("/") + "/"
    url = urljoin(base_url, normalized_target.lstrip("/"))

    digest_header = f"SHA-256={digest_value}"

    request_id = str(uuid.uuid4())
    timestamp = _format_iso_timestamp(timezone.now())
    signature = _compute_doku_signature(
        normalized_target,
        client_id=client_id,
        secret_key=secret_key,
        request_id=request_id,
        timestamp=timestamp,
        digest_header_value=digest_header,
    )

    headers = {
        "Client-Id": client_id,
        "Request-Id": request_id,
        "Request-Timestamp": timestamp,
        "Request-Target": normalized_target,
        "Signature": signature,
        "Digest": digest_header,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    request_obj = urllib_request.Request(url, data=body_bytes, headers=headers, method="POST")
    response_body = ""
    response_headers: dict[str, str] = {}

    try:
        with urllib_request.urlopen(request_obj, timeout=30) as response:
            response_body = response.read().decode("utf-8")
            response_status = response.status
            response_headers = dict(response.headers.items())
    except HTTPError as exc:  # pragma: no cover - network failures are hard to simulate
        response_body = exc.read().decode("utf-8", errors="replace")
        response_status = exc.code
        response_headers = dict(getattr(exc, "headers", {}) or {})
    except URLError as exc:  # pragma: no cover - network failures are hard to simulate
        raise RuntimeError(f"Gagal menghubungi DOKU: {exc.reason}") from exc

    if not response_body:
        response_data = {}
    else:
        try:
            response_data = json.loads(response_body)
        except json.JSONDecodeError:
            response_data = {"raw": response_body}

    if not (200 <= response_status < 300):
        logger.error(
            "DOKU API call to %s returned status %s with body: %s",
            normalized_target,
            response_status,
            response_body,
        )

    return response_status, response_data, response_headers


def _to_decimal(value) -> Decimal:
    try:
        return Decimal(value or 0)
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def _to_int_amount(value: Decimal) -> int:
    return int(_to_decimal(value).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _extract_order_number_from_midtrans(order_id: str | None) -> str:
    if not order_id:
        return ""
    separator = getattr(Order, "MIDTRANS_RETRY_SEPARATOR", "::retry::")
    if separator not in order_id:
        return order_id
    return order_id.split(separator, 1)[0]


def _extract_midtrans_error(exc: Exception, default_message: str) -> tuple[str, dict | None, int | None]:
    """Return a friendly error message and the raw payload if available."""

    response_payload = None
    status_code = None
    message = default_message

    payload_candidates = []
    for attr in ("api_response", "response", "body"):
        value = getattr(exc, attr, None)
        if value:
            payload_candidates.append(value)

    for payload in payload_candidates:
        data = payload
        if isinstance(data, bytes):
            try:
                data = data.decode("utf-8")
            except Exception:  # pragma: no cover - defensive
                data = data.decode("latin-1", errors="replace")
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except Exception:  # pragma: no cover - payload may not be JSON
                data = {"raw": data}

        if isinstance(data, dict):
            response_payload = data
            status_code = data.get("status_code") or data.get("status")

            message = (
                data.get("status_message")
                or data.get("message")
                or data.get("error_message")
                or data.get("error")
                or default_message
            )

            validation_messages = data.get("validation_messages")
            if not message and isinstance(validation_messages, list):
                message = "; ".join(map(str, validation_messages))
            break

    if (not response_payload) and hasattr(exc, "message"):
        maybe_message = getattr(exc, "message")
        if isinstance(maybe_message, str) and maybe_message.strip():
            message = maybe_message.strip()

    if (not response_payload) and not message:
        message = str(exc) or default_message

    return message, response_payload, status_code


def _build_midtrans_client():
    if midtransclient is None:
        raise RuntimeError("midtransclient library is not installed")
    if not settings.MIDTRANS_SERVER_KEY:
        raise RuntimeError("MIDTRANS_SERVER_KEY tidak dikonfigurasi")

    return midtransclient.Snap(
        is_production=settings.MIDTRANS_IS_PRODUCTION,
        server_key=settings.MIDTRANS_SERVER_KEY,
        client_key=settings.MIDTRANS_CLIENT_KEY,
    )


def _calculate_discount(
    subtotal: Decimal,
    shipping_cost: Decimal,
    shipping_method: str,
    discount_session: dict | None,
) -> tuple[Decimal, str]:
    discount_session = discount_session or {}
    discount_code = discount_session.get("code")

    if not discount_code:
        return Decimal("0"), ""

    discount_obj = DiscountCode.objects.filter(code__iexact=discount_code).first()
    if not discount_obj:
        return Decimal("0"), ""

    if not discount_obj.is_valid():
        return Decimal("0"), ""

    if not discount_obj.is_shipping_allowed(shipping_method):
        return Decimal("0"), ""

    grand_total = subtotal + shipping_cost
    if grand_total < discount_obj.get_min_spend():
        return Decimal("0"), ""

    discount_amount = discount_obj.calculate_discount(grand_total)
    if discount_amount > grand_total:
        discount_amount = grand_total

    return discount_amount, discount_obj.code.upper()


def _build_item_details(selected_items, shipping_cost: Decimal, discount_amount: Decimal, discount_code: str):
    details = []
    for item in selected_items:
        price = _to_int_amount(item.product.get_display_price())
        details.append(
            {
                "id": str(item.product.id),
                "price": price,
                "quantity": int(item.quantity),
                "name": item.product.name[:50],
            }
        )

    if shipping_cost > 0:
        details.append(
            {
                "id": "SHIPPING",
                "price": _to_int_amount(shipping_cost),
                "quantity": 1,
                "name": "Ongkos Kirim",
            }
        )

    if discount_amount > 0:
        details.append(
            {
                "id": "DISCOUNT",
                "price": -_to_int_amount(discount_amount),
                "quantity": 1,
                "name": f"Diskon {discount_code}".strip(),
            }
        )

    return details


def _ensure_midtrans_item_detail_total(
    item_details: list[dict],
    total_amount: Decimal,
) -> tuple[list[dict], int]:
    """Ensure item_details total matches the gross amount expected by Midtrans.

    Midtrans validates that the sum of (price * quantity) in item_details equals the
    ``gross_amount`` provided in ``transaction_details``. When product prices contain
    fractional Rupiah values, rounding each line item can cause mismatches that lead
    to HTTP 400 responses from the Snap API. This helper normalizes each detail entry
    and appends an adjustment line item when necessary so that the totals always
    match the rounded order total.
    """

    gross_amount = _to_int_amount(total_amount)
    normalized_details: list[dict] = []
    running_total = 0

    for detail in item_details or []:
        price = int(detail.get("price") or 0)
        quantity = int(detail.get("quantity") or 0) or 0
        if quantity <= 0:
            quantity = 1

        normalized_detail = dict(detail)
        normalized_detail["price"] = price
        normalized_detail["quantity"] = quantity
        normalized_details.append(normalized_detail)
        running_total += price * quantity

    difference = gross_amount - running_total
    if difference:
        normalized_details.append(
            {
                "id": "ADJUSTMENT",
                "name": "Penyesuaian Pembulatan",
                "price": difference,
                "quantity": 1,
            }
        )

    if not normalized_details and gross_amount:
        normalized_details.append(
            {
                "id": "TOTAL",
                "name": "Total Pesanan",
                "price": gross_amount,
                "quantity": 1,
            }
        )

    return normalized_details, gross_amount


def _build_customer_details(shipping_address: Address, user) -> dict:
    email = user.email or "customer@example.com"
    first_name = shipping_address.full_name or (user.get_full_name() or user.username)

    address_payload = {
        "first_name": first_name,
        "last_name": "",
        "email": email,
        "phone": shipping_address.phone,
        "address": shipping_address.get_full_address(),
        "city": shipping_address.city,
        "postal_code": shipping_address.postal_code,
        "country_code": "IDN",
    }

    return {
        "first_name": first_name,
        "last_name": "",
        "email": email,
        "phone": shipping_address.phone,
        "billing_address": address_payload,
        "shipping_address": address_payload,
    }


def _build_doku_line_items(
    selected_items,
    shipping_cost: Decimal,
    discount_amount: Decimal,
    total_amount: Decimal,
):
    has_discount = discount_amount and discount_amount > 0
    line_items = []

    for item in selected_items:
        product = getattr(item, "product", None)
        if product is None:
            continue
        quantity = int(getattr(item, "quantity", 0))
        if quantity <= 0:
            continue
        price = _to_int_amount(product.get_display_price())
        line_items.append(
            {
                "name": product.name[:50],
                "price": price,
                "quantity": quantity,
            }
        )

    if shipping_cost > 0:
        line_items.append(
            {
                "name": "Ongkos Kirim",
                "price": _to_int_amount(shipping_cost),
                "quantity": 1,
            }
        )

    # DOKU does not accept negative price items. When discounts are applied, omit line items
    # to avoid mismatched totals between payload and amount.
    total_amount_int = _to_int_amount(total_amount)
    if total_amount_int <= 0:
        return []

    if has_discount:
        return [
            {
                "name": "Total Pesanan",
                "price": total_amount_int,
                "quantity": 1,
            }
        ]

    return line_items


def _calculate_order_discount_amount(order: Order) -> Decimal:
    subtotal = _to_decimal(order.subtotal)
    shipping_cost = _to_decimal(order.shipping_cost)
    total = _to_decimal(order.total)
    discount = subtotal + shipping_cost - total
    if discount < 0:
        return Decimal("0")
    return discount


def _build_order_payment_item_details(order: Order) -> list[dict]:
    details: list[dict] = []
    for item in order.items.all():
        price = _to_int_amount(item.product_price)
        details.append(
            {
                "id": str(item.product_id or item.pk),
                "price": price,
                "quantity": int(item.quantity),
                "name": (item.product_name or "Produk")[:50],
            }
        )

    shipping_cost = _to_decimal(order.shipping_cost)
    if shipping_cost > 0:
        details.append(
            {
                "id": "SHIPPING",
                "price": _to_int_amount(shipping_cost),
                "quantity": 1,
                "name": "Ongkos Kirim",
            }
        )

    discount_amount = _calculate_order_discount_amount(order)
    if discount_amount > 0:
        details.append(
            {
                "id": "DISCOUNT",
                "price": -_to_int_amount(discount_amount),
                "quantity": 1,
                "name": "Diskon",
            }
        )

    return details


def _build_order_customer_details(order: Order) -> dict:
    shipping_address = order.shipping_address
    fallback_name = order.user.get_full_name() or order.user.username
    full_name = order.full_name or getattr(shipping_address, "full_name", "") or fallback_name
    email = order.email or order.user.email or "customer@example.com"
    phone = order.phone or getattr(shipping_address, "phone", "")
    address_text = (
        shipping_address.get_full_address()
        if shipping_address
        else (order.address or "")
    )
    city = order.city or getattr(shipping_address, "city", "")
    postal_code = order.postal_code or getattr(shipping_address, "postal_code", "")

    address_payload = {
        "first_name": full_name,
        "last_name": "",
        "email": email,
        "phone": phone,
        "address": address_text,
        "city": city,
        "postal_code": postal_code,
        "country_code": "IDN",
    }

    return {
        "first_name": full_name,
        "last_name": "",
        "email": email,
        "phone": phone,
        "billing_address": address_payload,
        "shipping_address": address_payload,
    }


def _build_order_customer_payload(order: Order) -> dict:
    customer_details = _build_order_customer_details(order)
    shipping_address = customer_details.get("shipping_address", {})
    return {
        "name": customer_details.get("first_name", ""),
        "email": customer_details.get("email", ""),
        "phone": customer_details.get("phone", ""),
        "address": shipping_address.get("address", ""),
    }


def _build_doku_line_items_from_order(order: Order) -> list[dict]:
    line_items: list[dict] = []

    for item in order.items.all():
        line_items.append(
            {
                "name": (item.product_name or "Produk")[:50],
                "price": _to_int_amount(item.product_price),
                "quantity": int(item.quantity),
            }
        )

    shipping_cost = _to_decimal(order.shipping_cost)
    if shipping_cost > 0:
        line_items.append(
            {
                "name": "Ongkos Kirim",
                "price": _to_int_amount(shipping_cost),
                "quantity": 1,
            }
        )

    discount_amount = _calculate_order_discount_amount(order)
    if discount_amount > 0:
        line_items.append(
            {
                "name": "Diskon",
                "price": -_to_int_amount(discount_amount),
                "quantity": 1,
            }
        )

    total_amount = _to_decimal(order.total)
    if total_amount <= 0:
        return []

    if not line_items:
        return [
            {
                "name": "Total Pesanan",
                "price": _to_int_amount(total_amount),
                "quantity": 1,
            }
        ]

    return line_items

@csrf_exempt
@login_required
@require_POST
def payment_create_snap_token(request):
    """Create a Midtrans Snap transaction token."""
    try:
        client_payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        client_payload = {}

    try:
        snap_client = _build_midtrans_client()
    except RuntimeError as exc:
        logger.exception("Midtrans configuration error: %s", exc)
        return JsonResponse({"message": str(exc)}, status=500)

    try:
        cart = _get_active_cart(request)
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Cart lookup failed: %s", exc)
        return JsonResponse({"message": "Keranjang tidak ditemukan."}, status=400)

    selected_items_qs = cart.items.filter(is_selected=True).select_related("product")
    if not selected_items_qs.exists():
        return JsonResponse({"message": "Tidak ada item yang dipilih untuk pembayaran."}, status=400)

    checkout_data = request.session.get("checkout", {})
    midtrans_slug = getattr(settings, "MIDTRANS_PAYMENT_METHOD_SLUG", "midtrans")
    selected_payment_slug = (checkout_data.get("payment_method") or "").strip().lower()
    if selected_payment_slug != (midtrans_slug or "").lower():
        logger.warning(
            "Attempt to create Midtrans token with unsupported payment method: %s",
            selected_payment_slug,
        )
        return JsonResponse(
            {"message": "Metode pembayaran ini tidak menggunakan Midtrans."},
            status=400,
        )
    address_id = checkout_data.get("address_id")
    payment_method_obj = (
        PaymentMethod.objects.filter(slug__iexact=selected_payment_slug).first()
        if selected_payment_slug
        else None
    )
    payment_method_obj = (
        PaymentMethod.objects.filter(slug__iexact=selected_payment_slug).first()
        if selected_payment_slug
        else None
    )
    shipping_address = (
        Address.objects.filter(id=address_id, user=request.user, is_deleted=False)
        .select_related("district")
        .first()
    )

    if not shipping_address:
        return JsonResponse({"message": "Alamat pengiriman tidak ditemukan."}, status=400)

    shipping_cost = _to_decimal(checkout_data.get("shipping_cost"))
    subtotal = _to_decimal(cart.get_selected_total())

    discount_amount, discount_code = _calculate_discount(
        subtotal,
        shipping_cost,
        checkout_data.get("shipping_method"),
        request.session.get("discount"),
    )

    total = subtotal + shipping_cost - discount_amount
    if total < 0:
        total = Decimal("0")

    # Validate client-provided totals if available
    client_total_value = client_payload.get("total")
    if client_total_value is not None:
        client_total = _to_decimal(client_total_value)
        if client_total != total:
            logger.warning(
                "Client total %s does not match server total %s",
                client_total,
                total,
            )

    selected_items, selected_quantities = _prepare_selected_cart_items(selected_items_qs)
    if not selected_items:
        return JsonResponse({"message": "Tidak ada item yang dipilih untuk pembayaran."}, status=400)

    for item in selected_items:
        quantity = selected_quantities.get(item.pk, item.quantity)
        if item.product.stock < quantity:
            return JsonResponse(
                {"message": f"Stok {item.product.name} tidak mencukupi."},
                status=400,
            )

    order_id = f"INV-{timezone.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"
    service_code = str(checkout_data.get("shipping_method") or "").upper()
    service_label = "Express" if service_code == "EXP" else "Reguler"
    district_name = getattr(getattr(shipping_address, "district", None), "name", "")
    eta = checkout_data.get("eta")
    notes = checkout_data.get("notes", "")

    token = None
    reused = False
    order = None
    try:
        with transaction.atomic():
            order = create_order_from_checkout(
                user=request.user,
                cart=cart,
                selected_items=selected_items,
                selected_quantities=selected_quantities,
                order_number=order_id,
                subtotal=subtotal,
                shipping_cost=shipping_cost,
                total=total,
                shipping_full_name=shipping_address.full_name,
                shipping_email=request.user.email,
                shipping_phone=shipping_address.phone,
                shipping_address_text=shipping_address.get_full_address(),
                shipping_city=shipping_address.city,
                shipping_postal_code=shipping_address.postal_code,
                courier_service=service_code,
                district_name=district_name,
                eta=eta,
                notes=notes,
                shipping_address_obj=shipping_address,
                shipping_service_name=service_label,
                payment_method_slug=selected_payment_slug,
                payment_method_display=(payment_method_obj.name if payment_method_obj else selected_payment_slug),
            )
            order_item_details = _build_order_payment_item_details(order)
            order_item_details, gross_amount = _ensure_midtrans_item_detail_total(
                order_item_details,
                order.total,
            )
            midtrans_order_id = order.ensure_midtrans_order_id()

            transaction_payload = {
                "transaction_details": {
                    "order_id": midtrans_order_id,
                    "gross_amount": gross_amount,
                },
                "item_details": order_item_details,
                "customer_details": _build_customer_details(shipping_address, request.user),
                "credit_card": {"secure": True},
                "callbacks": {
                    "finish": request.build_absolute_uri("/payment/finish/"),
                },
                "custom_field1": order.order_number,
            }

            token, reused = get_or_create_midtrans_snap_token(
                order=order,
                snap_client=snap_client,
                transaction_payload=transaction_payload,
            )
    except RuntimeError as exc:  # Token missing or business rule failure
        logger.warning("Failed to create Midtrans Snap transaction: %s", exc)
        return JsonResponse({"message": str(exc)}, status=400)
    except Exception as exc:  # pylint: disable=broad-except
        default_message = "Gagal membuat Snap Token."
        message, response_payload, status_code = _extract_midtrans_error(exc, default_message)
        log_extra = {"order_number": getattr(order, "order_number", None)}
        if response_payload:
            log_extra["midtrans_response"] = response_payload
        logger.exception("Failed to create order or Snap transaction: %s", exc, extra=log_extra)
        http_status = status_code if isinstance(status_code, int) and 400 <= status_code < 600 else 400
        return JsonResponse({"message": message or default_message}, status=http_status)

    request.session["midtrans_order_id"] = order.order_number
    request.session.pop("checkout", None)
    request.session.pop("discount", None)
    request.session.modified = True

    response_payload = {"token": token, "order_id": order.order_number}
    if reused:
        response_payload["reused"] = True

    return JsonResponse(response_payload)


@csrf_exempt
@login_required
@require_POST
def payment_create_doku_checkout(request):
    """Create a DOKU redirect checkout session."""

    checkout_data = request.session.get("checkout", {})
    doku_slug = getattr(settings, "DOKU_PAYMENT_METHOD_SLUG", "doku")
    selected_payment_slug = (checkout_data.get("payment_method") or "").strip().lower()
    if selected_payment_slug != (doku_slug or "").lower():
        return JsonResponse({"message": "Metode pembayaran ini tidak menggunakan DOKU."}, status=400)

    config = _get_doku_config()
    if not config.get("client_id") or not config.get("secret_key"):
        return JsonResponse({"message": "Konfigurasi DOKU belum lengkap."}, status=500)

    try:
        cart = _get_active_cart(request)
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Cart lookup failed: %s", exc)
        return JsonResponse({"message": "Keranjang tidak ditemukan."}, status=400)

    selected_items_qs = cart.items.filter(is_selected=True).select_related("product")
    if not selected_items_qs.exists():
        return JsonResponse({"message": "Tidak ada item yang dipilih untuk pembayaran."}, status=400)

    address_id = checkout_data.get("address_id")
    shipping_address = (
        Address.objects.filter(id=address_id, user=request.user, is_deleted=False)
        .select_related("district")
        .first()
    )

    if not shipping_address:
        return JsonResponse({"message": "Alamat pengiriman tidak ditemukan."}, status=400)

    shipping_cost = _to_decimal(checkout_data.get("shipping_cost"))
    subtotal = _to_decimal(cart.get_selected_total())

    discount_amount, discount_code = _calculate_discount(
        subtotal,
        shipping_cost,
        checkout_data.get("shipping_method"),
        request.session.get("discount"),
    )

    total = subtotal + shipping_cost - discount_amount
    if total < 0:
        total = Decimal("0")

    selected_items, selected_quantities = _prepare_selected_cart_items(selected_items_qs)
    if not selected_items:
        return JsonResponse({"message": "Tidak ada item yang dipilih untuk pembayaran."}, status=400)

    for item in selected_items:
        quantity = selected_quantities.get(item.pk, item.quantity)
        if item.product.stock < quantity:
            return JsonResponse(
                {"message": f"Stok {item.product.name} tidak mencukupi."},
                status=400,
            )

    order_id = f"INV-{timezone.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"
    service_code = str(checkout_data.get("shipping_method") or "").upper()
    service_label = "Express" if service_code == "EXP" else "Reguler"
    district_name = getattr(getattr(shipping_address, "district", None), "name", "")
    eta = checkout_data.get("eta")
    notes = checkout_data.get("notes", "")

    line_items = _build_doku_line_items(selected_items, shipping_cost, discount_amount, total)

    order_payload = {
        "amount": _to_int_amount(total),
        "invoice_number": order_id,
        "currency": "IDR",
        "callback_url": request.build_absolute_uri(reverse("payment:doku_notification")),
        "return_url": request.build_absolute_uri(reverse("payment:doku_return")),
    }
    if config.get("merchant_code"):
        order_payload["merchant_code"] = config["merchant_code"]
    if line_items:
        order_payload["line_items"] = line_items

    customer_details = _build_customer_details(shipping_address, request.user)
    customer_payload = {
        "name": customer_details.get("first_name", ""),
        "email": customer_details.get("email", ""),
        "phone": customer_details.get("phone", ""),
        "address": shipping_address.get_full_address(),
    }

    payload = {
        "order": order_payload,
        "payment": {"payment_due_date": 60},
        "customer": customer_payload,
        "additional_info": {
            "notes": notes,
            "shipping_service": service_label,
            "discount_code": discount_code or "",
        },
    }

    order = None
    try:
        with transaction.atomic():
            order = create_order_from_checkout(
                user=request.user,
                cart=cart,
                selected_items=selected_items,
                selected_quantities=selected_quantities,
                order_number=order_id,
                subtotal=subtotal,
                shipping_cost=shipping_cost,
                total=total,
                shipping_full_name=shipping_address.full_name,
                shipping_email=request.user.email,
                shipping_phone=shipping_address.phone,
                shipping_address_text=shipping_address.get_full_address(),
                shipping_city=shipping_address.city,
                shipping_postal_code=shipping_address.postal_code,
                courier_service=service_code,
                district_name=district_name,
                eta=eta,
                notes=notes,
                shipping_address_obj=shipping_address,
                shipping_service_name=service_label,
                payment_method_slug=selected_payment_slug,
                payment_method_display=(payment_method_obj.name if payment_method_obj else selected_payment_slug),
            )

            status_code, response_data, _ = _call_doku_api("/checkout/v1/payment", payload)
            if not (200 <= status_code < 300):
                message = response_data.get("message") or response_data.get("error")
                raise RuntimeError(message or "Gagal membuat sesi pembayaran DOKU.")

            payment_url = (
                response_data.get("payment_url")
                or response_data.get("redirect_url")
                or response_data.get("checkout_url")
                or response_data.get("response", {}).get("payment", {}).get("url")
                or response_data.get("response", {}).get("payment", {}).get("payment_url")
            )

            if not payment_url:
                raise RuntimeError("URL pembayaran DOKU tidak tersedia.")

    except RuntimeError as exc:
        logger.exception("Failed to create DOKU checkout: %s", exc)
        return JsonResponse({"message": str(exc)}, status=500)
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Failed to create order or DOKU checkout: %s", exc)
        return JsonResponse({"message": "Gagal membuat sesi pembayaran DOKU."}, status=500)

    request.session["doku_order_id"] = order.order_number
    request.session.pop("checkout", None)
    request.session.pop("discount", None)
    request.session.modified = True

    return JsonResponse({"payment_url": payment_url, "order_id": order.order_number})


@login_required
@require_POST
def payment_create_order_snap_token(request, order_number):
    """Create a Midtrans Snap token for an existing pending order."""

    try:
        snap_client = _build_midtrans_client()
    except RuntimeError as exc:
        logger.exception("Midtrans configuration error: %s", exc)
        return JsonResponse({"message": str(exc)}, status=500)

    order = (
        Order.objects.filter(order_number=order_number, user=request.user)
        .select_related("shipping_address")
        .prefetch_related("items")
        .first()
    )

    if order is None:
        return JsonResponse({"message": "Pesanan tidak ditemukan."}, status=404)

    if cancel_order_due_to_timeout(order):
        return JsonResponse({"message": "Batas waktu pembayaran telah berakhir."}, status=400)

    if order.status != "pending":
        return JsonResponse({"message": "Pesanan tidak dapat dibayar."}, status=400)

    midtrans_slug = getattr(settings, "MIDTRANS_PAYMENT_METHOD_SLUG", "midtrans")
    if (order.payment_method or "").lower() != (midtrans_slug or "").lower():
        return JsonResponse({"message": "Metode pembayaran pesanan tidak menggunakan Midtrans."}, status=400)

    midtrans_order_id = order.ensure_midtrans_order_id()

    order_item_details = _build_order_payment_item_details(order)
    order_item_details, gross_amount = _ensure_midtrans_item_detail_total(order_item_details, order.total)

    transaction_payload = {
        "transaction_details": {
            "order_id": midtrans_order_id,
            "gross_amount": gross_amount,
        },
        "item_details": order_item_details,
        "customer_details": _build_order_customer_details(order),
        "credit_card": {"secure": True},
        "callbacks": {
            "finish": request.build_absolute_uri(reverse("payment:finish")),
        },
        "custom_field1": order.order_number,
    }

    try:
        token, reused = get_or_create_midtrans_snap_token(
            order=order,
            snap_client=snap_client,
            transaction_payload=transaction_payload,
        )
    except Exception as exc:  # pylint: disable=broad-except
        default_message = "Gagal membuat token pembayaran."
        message, response_payload, status_code = _extract_midtrans_error(exc, default_message)
        log_extra = {"order_number": order.order_number, "midtrans_order_id": order.midtrans_order_id}
        if response_payload:
            log_extra["midtrans_response"] = response_payload
        logger.exception(
            "Failed to create Midtrans transaction for order %s: %s",
            order.order_number,
            exc,
            extra=log_extra,
        )
        http_status = status_code if isinstance(status_code, int) and 400 <= status_code < 600 else 500
        return JsonResponse({"message": message or default_message}, status=http_status)

    return JsonResponse({"token": token, "order_id": order.order_number, "reused": reused})


@login_required
@require_POST
def payment_create_order_doku_checkout(request, order_number):
    """Create a DOKU payment session for an existing pending order."""

    config = _get_doku_config()
    if not config.get("client_id") or not config.get("secret_key"):
        return JsonResponse({"message": "Konfigurasi DOKU belum lengkap."}, status=500)

    order = (
        Order.objects.filter(order_number=order_number, user=request.user)
        .select_related("shipping_address")
        .prefetch_related("items")
        .first()
    )

    if order is None:
        return JsonResponse({"message": "Pesanan tidak ditemukan."}, status=404)

    if cancel_order_due_to_timeout(order):
        return JsonResponse({"message": "Batas waktu pembayaran telah berakhir."}, status=400)

    if order.status != "pending":
        return JsonResponse({"message": "Pesanan tidak dapat dibayar."}, status=400)

    doku_slug = getattr(settings, "DOKU_PAYMENT_METHOD_SLUG", "doku")
    if (order.payment_method or "").lower() != (doku_slug or "").lower():
        return JsonResponse({"message": "Metode pembayaran pesanan tidak menggunakan DOKU."}, status=400)

    line_items = _build_doku_line_items_from_order(order)
    order_payload = {
        "amount": _to_int_amount(order.total),
        "invoice_number": order.order_number,
        "currency": "IDR",
        "callback_url": request.build_absolute_uri(reverse("payment:doku_notification")),
        "return_url": request.build_absolute_uri(reverse("payment:doku_return")),
    }
    if config.get("merchant_code"):
        order_payload["merchant_code"] = config["merchant_code"]
    if line_items:
        order_payload["line_items"] = line_items

    customer_payload = _build_order_customer_payload(order)
    service_label = order.selected_service_name or (
        "Express" if str(order.selected_courier or "").upper() == "EXP" else "Reguler"
    )

    payload = {
        "order": order_payload,
        "payment": {"payment_due_date": 60},
        "customer": customer_payload,
        "additional_info": {
            "notes": order.notes,
            "shipping_service": service_label,
            "discount_code": "",
        },
    }

    try:
        status_code, response_data, _ = _call_doku_api("/checkout/v1/payment", payload)
    except RuntimeError as exc:
        logger.exception("Failed to call DOKU API for order %s: %s", order.order_number, exc)
        return JsonResponse({"message": str(exc)}, status=500)

    if not (200 <= status_code < 300):
        message = response_data.get("message") or response_data.get("error")
        logger.error("DOKU retry checkout failed for %s: %s", order.order_number, response_data)
        return JsonResponse({"message": message or "Gagal membuat sesi pembayaran DOKU."}, status=500)

    payment_url = (
        response_data.get("payment_url")
        or response_data.get("redirect_url")
        or response_data.get("checkout_url")
        or response_data.get("response", {}).get("payment", {}).get("url")
        or response_data.get("response", {}).get("payment", {}).get("payment_url")
    )

    if not payment_url:
        return JsonResponse({"message": "URL pembayaran DOKU tidak tersedia."}, status=500)

    return JsonResponse({"payment_url": payment_url, "order_id": order.order_number})


@csrf_exempt
@login_required
@require_POST
def payment_finish(request):
    """Receive payment result callbacks from the frontend and update order status."""
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"message": "Payload tidak valid."}, status=400)

    result = payload.get("result") or payload
    raw_order_id = result.get("order_id")
    order_id = _extract_order_number_from_midtrans(raw_order_id)
    transaction_status = result.get("transaction_status") or result.get("status")

    if not order_id:
        return JsonResponse({"message": "Order ID tidak ditemukan."}, status=400)

    order = Order.objects.filter(order_number=order_id).first()
    if order and transaction_status:
        success_states = {"capture", "settlement"}
        pending_states = {"pending"}
        failure_states = {"deny", "cancel", "expire", "failure"}

        if transaction_status in success_states and order.status != "paid":
            order.status = "paid"
            update_fields = ["status"]
            if order.midtrans_token:
                order.midtrans_token = ""
                update_fields.append("midtrans_token")
            order.save(update_fields=update_fields)
        elif transaction_status in pending_states and order.status != "pending":
            order.status = "pending"
            order.save(update_fields=["status"])
        elif transaction_status in failure_states and order.status != "cancelled":
            with transaction.atomic():
                restore_order_stock(order)
                order.status = "cancelled"
                update_fields = ["status"]
                if order.midtrans_token:
                    order.midtrans_token = ""
                    update_fields.append("midtrans_token")
                order.save(update_fields=update_fields)

    request.session["midtrans_last_result"] = result
    request.session.modified = True

    response_payload = {"message": "Status pembayaran diterima.", "order_id": order_id}
    if raw_order_id and raw_order_id != order_id:
        response_payload["gateway_order_id"] = raw_order_id
    if order:
        response_payload["status"] = order.status

    return JsonResponse(response_payload)


@csrf_exempt
@require_POST
def doku_notification(request):
    """Handle asynchronous payment status notifications from DOKU."""

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"message": "Payload tidak valid."}, status=400)

    order_info = payload.get("order") or {}
    raw_order_id = (
        order_info.get("invoice_number")
        or order_info.get("order_id")
        or payload.get("order_id")
    )
    order_id = _extract_order_number_from_midtrans(raw_order_id)
    status_info = payload.get("transaction") or payload.get("payment") or {}
    transaction_status = (
        status_info.get("status")
        or status_info.get("transaction_status")
        or payload.get("transaction_status")
        or payload.get("status")
    )

    if not order_id:
        return JsonResponse({"message": "Order ID tidak ditemukan."}, status=400)

    order = Order.objects.filter(order_number=order_id).first()
    if order is None:
        return JsonResponse({"message": "Pesanan tidak ditemukan."}, status=404)

    normalized_status = (transaction_status or "").strip().upper()
    success_states = {"SUCCESS", "COMPLETED", "PAID"}
    pending_states = {"PENDING", "WAITING", "IN_PROGRESS"}
    failure_states = {"FAILED", "CANCELLED", "EXPIRED", "VOID"}

    if normalized_status in success_states and order.status != "paid":
        order.status = "paid"
        order.save(update_fields=["status"])
    elif normalized_status in pending_states and order.status != "pending":
        order.status = "pending"
        order.save(update_fields=["status"])
    elif normalized_status in failure_states and order.status != "cancelled":
        with transaction.atomic():
            restore_order_stock(order)
            order.status = "cancelled"
            order.save(update_fields=["status"])

    request.session["doku_last_result"] = payload
    request.session.modified = True

    response_payload = {"message": "Status pembayaran DOKU diterima.", "order_id": order_id}
    if raw_order_id and raw_order_id != order_id:
        response_payload["gateway_order_id"] = raw_order_id
    if order:
        response_payload["status"] = order.status

    return JsonResponse(response_payload)


@login_required
def doku_return(request):
    """Redirect handler after the customer completes DOKU payment."""

    status_param = (
        request.GET.get("status")
        or request.GET.get("transaction_status")
        or request.GET.get("state")
        or ""
    ).strip().upper()
    order_id = request.GET.get("order_id") or request.GET.get("invoice_number")
    session_order_id = request.session.pop("doku_order_id", None)
    order_reference = order_id or session_order_id

    if status_param == "SUCCESS":
        message = "Pembayaran berhasil diproses."
        messages.success(request, message)
    elif status_param == "PENDING":
        message = "Pembayaran sedang diproses. Silakan selesaikan pembayaran Anda."
        messages.warning(request, message)
    elif status_param:
        message = "Pembayaran tidak berhasil atau dibatalkan."
        messages.error(request, message)
    else:
        messages.info(request, "Status pembayaran DOKU belum diketahui. Periksa riwayat pesanan Anda.")

    if order_reference:
        request.session["doku_last_order"] = order_reference
        request.session.modified = True

    return redirect(reverse("core:order_list"))
