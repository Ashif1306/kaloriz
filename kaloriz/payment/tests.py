import uuid
from decimal import Decimal
from unittest import mock
import uuid

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from core.models import Order
from payment import views
from payment.services import get_or_create_snap_token


class MidtransItemDetailAlignmentTests(SimpleTestCase):
    def test_item_details_remain_unchanged_when_totals_match(self):
        details = [
            {"id": "SKU1", "name": "Produk A", "price": 5000, "quantity": 2},
            {"id": "SHIP", "name": "Ongkos Kirim", "price": 1000, "quantity": 1},
        ]
        adjusted, gross_amount = views._ensure_midtrans_item_detail_total(details, Decimal("11000"))

        self.assertEqual(gross_amount, 11000)
        self.assertEqual(adjusted, details)

    def test_item_details_receive_adjustment_when_rounding_mismatch_occurs(self):
        details = [
            {"id": "SKU1", "name": "Produk A", "price": 11, "quantity": 2},
        ]
        adjusted, gross_amount = views._ensure_midtrans_item_detail_total(details, Decimal("21.00"))

        self.assertEqual(gross_amount, 21)
        self.assertEqual(len(adjusted), 2)
        adjustment = adjusted[-1]
        self.assertEqual(adjustment["id"], "ADJUSTMENT")
        self.assertEqual(adjustment["price"], -1)
        self.assertEqual(adjustment["quantity"], 1)


class MidtransSnapTokenServiceTests(TestCase):
    """Ensure token reuse/regeneration logic behaves as expected."""

    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="snapper",
            email="buyer@example.com",
            password="secret",
        )

    def _create_order(self, **overrides) -> Order:
        default_kwargs = {
            "user": self.user,
            "order_number": overrides.pop(
                "order_number", f"INV-{uuid.uuid4().hex[:8].upper()}"
            ),
            "payment_method": "midtrans",
            "payment_method_display": "Midtrans",
            "full_name": "Test Buyer",
            "email": "buyer@example.com",
            "phone": "08123456789",
            "address": "Jalan Mawar No. 1",
            "city": "Jakarta",
            "postal_code": "12345",
            "subtotal": Decimal("100000"),
            "shipping_cost": Decimal("0"),
            "total": Decimal("100000"),
        }
        default_kwargs.update(overrides)
        return Order.objects.create(**default_kwargs)

    def _build_payload(self):
        return {"transaction_details": {}, "item_details": [], "customer_details": {}}

    def test_reuses_existing_token_when_order_pending(self):
        order = self._create_order(
            midtrans_order_id="KALORIZ-1",
            midtrans_snap_token="existing-token",
            midtrans_retry=1,
        )

        snap_client = mock.Mock()
        token, reused = get_or_create_snap_token(
            order=order,
            snap_client=snap_client,
            base_payload=self._build_payload(),
        )

        self.assertEqual(token, "existing-token")
        self.assertTrue(reused)
        snap_client.create_transaction.assert_not_called()

    def test_generates_retry_suffix_when_requesting_new_token(self):
        order = self._create_order(
            midtrans_order_id="KALORIZ-1",
            midtrans_retry=1,
        )
        snap_client = mock.Mock()
        snap_client.create_transaction.return_value = {"token": "new-token"}

        token, reused = get_or_create_snap_token(
            order=order,
            snap_client=snap_client,
            base_payload=self._build_payload(),
        )

        order.refresh_from_db()
        self.assertEqual(token, "new-token")
        self.assertFalse(reused)
        self.assertTrue(order.midtrans_order_id.endswith(f"{Order.MIDTRANS_RETRY_SEPARATOR}1"))
        self.assertEqual(order.midtrans_retry, 2)
        self.assertEqual(order.midtrans_snap_token, "new-token")
        snap_client.create_transaction.assert_called_once()

    def test_creates_token_with_base_id_when_first_time(self):
        order = self._create_order()
        snap_client = mock.Mock()
        snap_client.create_transaction.return_value = {"token": "fresh-token"}

        token, reused = get_or_create_snap_token(
            order=order,
            snap_client=snap_client,
            base_payload=self._build_payload(),
        )

        order.refresh_from_db()
        self.assertEqual(token, "fresh-token")
        self.assertFalse(reused)
        self.assertIsNotNone(order.midtrans_order_id)
        self.assertEqual(order.midtrans_retry, 1)
        self.assertEqual(order.midtrans_snap_token, "fresh-token")
        snap_client.create_transaction.assert_called_once()
