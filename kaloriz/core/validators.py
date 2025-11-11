"""
Validators untuk memastikan data siap untuk perhitungan ongkir
"""
from django.conf import settings


def validate_ready_for_shipping(order):
    """
    Validasi bahwa order siap untuk perhitungan ongkir.

    Args:
        order: Order object yang akan divalidasi

    Raises:
        AssertionError: Jika ada data yang belum lengkap

    Example:
        >>> from core.validators import validate_ready_for_shipping
        >>> validate_ready_for_shipping(order)
    """
    # Pastikan alamat pengiriman sudah dipilih
    assert order.shipping_address, "Alamat pengiriman belum dipilih."

    # Pastikan alamat punya ID kecamatan tujuan
    assert order.shipping_address.destination_subdistrict_id, \
        "Alamat belum memiliki ID kecamatan tujuan."

    # Pastikan total berat minimal 1000 gram (1 kg)
    assert order.total_weight_gram >= 1000, \
        "Total berat minimal 1000 gram (1 kg)."

    # Validasi kurir yang dipilih (opsional, jika sudah ada pilihan kurir)
    if order.selected_courier:
        assert order.selected_courier in settings.SUPPORTED_COURIERS, \
            f"Kurir '{order.selected_courier}' tidak didukung. " \
            f"Kurir yang didukung: {', '.join(settings.SUPPORTED_COURIERS)}"

    return True
