from decimal import Decimal

from django.test import SimpleTestCase

from payment import views


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
