"""Helper functions for payment workflows."""
from __future__ import annotations

import base64
import json
import logging
from typing import Tuple
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request

from django.conf import settings

from core.models import Order

logger = logging.getLogger(__name__)

_RETRYABLE_STATUSES = {"expire", "cancel", "deny", "failure"}


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


def _should_refresh_midtrans_token(status_payload: dict | None) -> bool:
    if not status_payload:
        return False
    transaction_status = (status_payload.get("transaction_status") or "").lower()
    return transaction_status in _RETRYABLE_STATUSES


def get_or_create_midtrans_snap_token(
    *, order: Order, snap_client, transaction_payload: dict
) -> Tuple[str, bool]:
    """Return an existing Snap token or create a new one when needed."""

    verify_before_reuse = getattr(settings, "MIDTRANS_VERIFY_STATUS_BEFORE_REUSE", True)

    if order.midtrans_token:
        if verify_before_reuse:
            status_payload = fetch_midtrans_transaction_status(order.midtrans_order_id)
            if not _should_refresh_midtrans_token(status_payload):
                return order.midtrans_token, True
            order.regenerate_midtrans_order_id()
        else:
            return order.midtrans_token, True

    ensured_order_id = order.ensure_midtrans_order_id()
    payload = dict(transaction_payload or {})
    transaction_details = dict(payload.get("transaction_details") or {})
    transaction_details["order_id"] = order.midtrans_order_id or ensured_order_id
    payload["transaction_details"] = transaction_details

    snap_response = snap_client.create_transaction(payload)
    token = snap_response.get("token")
    if not token:
        raise RuntimeError("Token Snap tidak tersedia.")

    order.midtrans_token = token
    order.save(update_fields=["midtrans_token"])
    return token, False
