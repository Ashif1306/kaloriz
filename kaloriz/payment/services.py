"""Helper functions for payment workflows."""
from __future__ import annotations

import base64
import json
import logging
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Tuple
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request

from django.conf import settings

from core.models import Order

logger = logging.getLogger(__name__)


def _to_int_amount(value) -> int:
    try:
        decimal_value = Decimal(value or 0)
    except (InvalidOperation, TypeError, ValueError):
        decimal_value = Decimal("0")
    quantized = decimal_value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(quantized)


def fetch_midtrans_transaction_status(order_id: str) -> dict | None:
    """Fetch the latest Midtrans transaction status for the given order_id."""

    if not order_id or not getattr(settings, "MIDTRANS_SERVER_KEY", ""):
        return None

    base_url = "https://api.midtrans.com" if settings.MIDTRANS_IS_PRODUCTION else "https://api.sandbox.midtrans.com"
    encoded_order_id = urllib_parse.quote(order_id, safe="")
    url = f"{base_url}/v2/{encoded_order_id}/status"

    credentials = f"{settings.MIDTRANS_SERVER_KEY}:".encode("utf-8")
    authorization = base64.b64encode(credentials).decode("utf-8")

    request_obj = urllib_request.Request(url, method="GET")
    request_obj.add_header("Authorization", f"Basic {authorization}")
    request_obj.add_header("Accept", "application/json")

    try:
        with urllib_request.urlopen(request_obj, timeout=15) as response:
            raw_body = response.read().decode("utf-8")
    except urllib_error.HTTPError as exc:  # pragma: no cover - network failures hard to simulate
        raw_body = exc.read().decode("utf-8", errors="replace")
        if exc.code == 404:
            logger.info("Midtrans status for %s not found", order_id)
            return None
    except urllib_error.URLError as exc:  # pragma: no cover - network failures hard to simulate
        logger.warning("Failed to fetch Midtrans status for %s: %s", order_id, exc)
        return None

    if not raw_body:
        return None

    try:
        return json.loads(raw_body)
    except json.JSONDecodeError:  # pragma: no cover - defensive
        logger.warning("Failed to parse Midtrans status response for %s: %s", order_id, raw_body)
        return None


def _split_midtrans_order_id(order: Order) -> tuple[str | None, int]:
    """Return the base order ID and last retry extracted from the stored value."""

    current_id = (order.midtrans_order_id or "").strip() or None
    separators = [getattr(Order, "MIDTRANS_RETRY_SEPARATOR", "-R")]
    legacy = getattr(Order, "MIDTRANS_LEGACY_RETRY_SEPARATORS", ("::retry::",))
    separators.extend(filter(None, legacy))

    if not current_id:
        return None, 0

    for separator in separators:
        if separator and separator in current_id:
            base, suffix = current_id.split(separator, 1)
            try:
                retry_value = int(suffix)
            except (TypeError, ValueError):
                retry_value = 0
            return (base or None), retry_value

    return current_id, 0


def _build_midtrans_base_id(order: Order) -> str:
    try:
        base_id = order.get_midtrans_base_order_id()
    except AttributeError:  # pragma: no cover - legacy safety
        prefix = getattr(settings, "MIDTRANS_ORDER_ID_PREFIX", getattr(Order, "MIDTRANS_ORDER_ID_PREFIX", "KALORIZ"))
        prefix = (prefix or "KALORIZ").strip()
        base_id = f"{prefix}-{order.pk}"
    return base_id


def _compose_midtrans_order_id(order: Order, base_id: str, retry_index: int) -> str:
    field = order._meta.get_field("midtrans_order_id")
    max_length = getattr(field, "max_length", 50)
    separator = getattr(Order, "MIDTRANS_RETRY_SEPARATOR", "-R")
    normalized_base = (base_id or _build_midtrans_base_id(order))[:max_length]

    if retry_index <= 0 or not separator:
        return normalized_base

    suffix = f"{separator}{retry_index}"
    if len(suffix) >= max_length:
        return suffix[-max_length:]

    allowed_base_length = max_length - len(suffix)
    trimmed_base = normalized_base[:allowed_base_length]
    if not trimmed_base:
        trimmed_base = normalized_base[-allowed_base_length:]

    return f"{trimmed_base}{suffix}"


def _clone_payload(base_payload: dict | None) -> dict:
    payload = dict(base_payload or {})
    payload["transaction_details"] = dict(payload.get("transaction_details") or {})
    payload["item_details"] = list(payload.get("item_details") or [])
    payload["customer_details"] = dict(payload.get("customer_details") or {})
    return payload


def get_or_create_snap_token(*, order: Order, snap_client, base_payload: dict) -> Tuple[str, bool]:
    """Return a reusable Midtrans Snap token or mint a new one."""

    is_pending = (order.status or "").lower() == "pending"
    existing_token = (order.midtrans_snap_token or "").strip()

    if existing_token and is_pending:
        return existing_token, True

    if existing_token and not is_pending:
        order.clear_midtrans_snap_token()

    base_id, retry_from_id = _split_midtrans_order_id(order)
    base_id = base_id or _build_midtrans_base_id(order)
    retry_index = order.midtrans_retry or retry_from_id or 0
    candidate_order_id = _compose_midtrans_order_id(order, base_id, retry_index)

    payload = _clone_payload(base_payload)
    transaction_details = payload.get("transaction_details", {})
    transaction_details["order_id"] = candidate_order_id
    transaction_details["gross_amount"] = _to_int_amount(order.total)
    payload["transaction_details"] = transaction_details

    snap_response = snap_client.create_transaction(payload)
    token = snap_response.get("token")
    if not token:
        raise RuntimeError("Token Snap tidak tersedia.")

    order.midtrans_order_id = candidate_order_id
    order.midtrans_snap_token = token
    order.midtrans_retry = retry_index + 1
    order.save(update_fields=["midtrans_order_id", "midtrans_snap_token", "midtrans_retry"])

    return token, False
