import uuid
from decimal import Decimal
from unittest import mock

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

    @mock.patch("payment.services.fetch_midtrans_transaction_status")
    def test_reuses_existing_token_when_midtrans_status_pending(self, mock_status):
        order = self._create_order()
        order.ensure_midtrans_order_id()
        order.midtrans_token = "existing-token"
        order.save(update_fields=["midtrans_token"])

        mock_status.return_value = {"transaction_status": "pending"}
        snap_client = mock.Mock()

        token, reused = get_or_create_snap_token(
            order=order,
            snap_client=snap_client,
            transaction_payload={"transaction_details": {}},
        )

        self.assertEqual(token, "existing-token")
        self.assertTrue(reused)
        snap_client.create_transaction.assert_not_called()

    @mock.patch("payment.services.fetch_midtrans_transaction_status")
    def test_regenerates_order_id_when_previous_transaction_expired(self, mock_status):
        order = self._create_order()
        original_order_id = order.ensure_midtrans_order_id()
        order.midtrans_token = "expired-token"
        order.save(update_fields=["midtrans_token"])

        mock_status.return_value = {"transaction_status": "expire"}
        snap_client = mock.Mock()
        snap_client.create_transaction.return_value = {"token": "new-token"}

        token, reused = get_or_create_snap_token(
            order=order,
            snap_client=snap_client,
            transaction_payload={"transaction_details": {}},
        )

        order.refresh_from_db()
        self.assertEqual(token, "new-token")
        self.assertFalse(reused)
        self.assertEqual(order.midtrans_token, "new-token")
        self.assertNotEqual(order.midtrans_order_id, original_order_id)
        self.assertIn(Order.MIDTRANS_RETRY_SEPARATOR, order.midtrans_order_id)
        snap_client.create_transaction.assert_called_once()

    def test_creates_token_when_one_does_not_exist(self):
        order = self._create_order()
        original_order_id = order.ensure_midtrans_order_id()
        snap_client = mock.Mock()
        snap_client.create_transaction.return_value = {"token": "fresh-token"}

        token, reused = get_or_create_snap_token(
            order=order,
            snap_client=snap_client,
            transaction_payload={"transaction_details": {}},
        )

        order.refresh_from_db()
        self.assertEqual(token, "fresh-token")
        self.assertFalse(reused)
        self.assertEqual(order.midtrans_token, "fresh-token")
        self.assertEqual(order.midtrans_order_id, original_order_id)
        snap_client.create_transaction.assert_called_once()
