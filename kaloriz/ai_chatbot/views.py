import logging
import re
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from decimal import Decimal

from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import Q

from ai_chatbot.services.openrouter_client import ask_ai_with_priority
from ai_chatbot.utils.intent_classifier import classify_intent
from catalog.models import Product
from core.models import Order
from shipping.models import District

logger = logging.getLogger(__name__)

DAY_NAMES = {
    0: "Senin",
    1: "Selasa",
    2: "Rabu",
    3: "Kamis",
    4: "Jumat",
    5: "Sabtu",
    6: "Minggu",
}

MONTH_NAMES = {
    1: "Januari",
    2: "Februari",
    3: "Maret",
    4: "April",
    5: "Mei",
    6: "Juni",
    7: "Juli",
    8: "Agustus",
    9: "September",
    10: "Oktober",
    11: "November",
    12: "Desember",
}


def _format_tanggal(dt: datetime) -> tuple[str, str, str]:
    hari = DAY_NAMES[dt.weekday()]
    bulan = MONTH_NAMES[dt.month]
    tanggal = f"{dt.day} {bulan} {dt.year}"
    waktu = dt.strftime("%H:%M")
    return hari, tanggal, waktu


def jawab_tanggal(user_message: str) -> str | None:
    """Jawab pertanyaan terkait tanggal/hari dalam Bahasa Indonesia."""

    normalized = (user_message or "").lower()
    if not normalized:
        return None

    now = datetime.now()

    keywords = (
        "hari ini",
        "sekarang",
        "tanggal berapa",
        "hari apa",
        "besok",
        "lusa",
        "tanggal",
    )

    has_date_question = any(key in normalized for key in keywords)

    if not has_date_question and not re.search(
        r"\b(3[01]|[12]?\d)\s+([a-zA-Z]+)(?:\s+(\d{4}))?\b", normalized
    ):
        return None

    if (
        "hari ini" in normalized
        or "sekarang" in normalized
        or "tanggal berapa" in normalized
        or "hari apa" in normalized
        or "tanggal" in normalized
    ):
        hari, tanggal, waktu = _format_tanggal(now)
        return f"Hari ini adalah {hari}, {tanggal} pukul {waktu}."

    if "besok" in normalized:
        besok = now + timedelta(days=1)
        hari, tanggal, _ = _format_tanggal(besok)
        return f"Besok adalah {hari}, {tanggal}."

    if "lusa" in normalized:
        lusa = now + timedelta(days=2)
        hari, tanggal, _ = _format_tanggal(lusa)
        return f"Lusa adalah {hari}, {tanggal}."

    month_lookup = {name.lower(): num for num, name in MONTH_NAMES.items()}
    match = re.search(r"\b(3[01]|[12]?\d)\s+([a-zA-Z]+)(?:\s+(\d{4}))?\b", normalized)
    if match:
        day_str, month_str, year_str = match.groups()
        month_num = month_lookup.get(month_str.lower())
        if month_num:
            year = int(year_str) if year_str else now.year
            try:
                target_date = datetime(year, month_num, int(day_str))
            except ValueError:
                return None

            hari, tanggal, _ = _format_tanggal(target_date)
            return f"Tanggal {tanggal} jatuh pada hari {hari}."

    return None


def format_currency(amount: Decimal) -> str:
    """Format Decimal to Indonesian Rupiah style (Rp XX.XXX)."""

    try:
        rounded = int(Decimal(amount).quantize(Decimal("1")))
    except (TypeError, ValueError):
        return "Rp 0"

    return f"Rp {rounded:,}".replace(",", ".")


def format_datetime_id():
    """Format datetime sekarang ke gaya Bahasa Indonesia."""

    now = datetime.now()
    hari_list = [
        "Senin",
        "Selasa",
        "Rabu",
        "Kamis",
        "Jumat",
        "Sabtu",
        "Minggu",
    ]
    bulan_list = [
        "Januari",
        "Februari",
        "Maret",
        "April",
        "Mei",
        "Juni",
        "Juli",
        "Agustus",
        "September",
        "Oktober",
        "November",
        "Desember",
    ]

    hari = hari_list[now.weekday()]
    bulan = bulan_list[now.month - 1]
    tanggal = f"{now.day} {bulan} {now.year}"
    waktu = now.strftime("%H:%M")

    return {
        "hari": hari,
        "tanggal": tanggal,
        "tanggal_lengkap": f"{hari}, {tanggal} pukul {waktu}",
        "waktu": waktu,
    }


def get_district_from_text(message: str):
    """Cari kecamatan yang disebutkan user berdasarkan kedekatan teks."""

    normalized = (message or "").lower()
    if not normalized:
        return None, 0.0

    districts = list(District.objects.filter(is_active=True))

    direct_matches = [d for d in districts if d.name.lower() in normalized]
    if direct_matches:
        if len(direct_matches) == 1:
            return direct_matches[0], 1.0

        best_direct = max(
            direct_matches,
            key=lambda d: SequenceMatcher(None, normalized, d.name.lower()).ratio(),
        )
        best_score = SequenceMatcher(None, normalized, best_direct.name.lower()).ratio()
        return best_direct, best_score

    best_match = None
    best_score = 0.0
    for district in districts:
        score = SequenceMatcher(None, normalized, district.name.lower()).ratio()
        if score > best_score:
            best_match = district
            best_score = score

    # Kembalikan kecamatan paling mirip jika skornya cukup tinggi
    return (best_match if best_score >= 0.6 else None), best_score


def get_order_identifier(order) -> str:
    """Get the most relevant order identifier available on the model."""

    return (
        getattr(order, "order_number", "")
        or getattr(order, "invoice", "")
        or getattr(order, "invoice_code", "")
        or getattr(order, "invoice_no", "")
        or getattr(order, "midtrans_order_id", "")
        or str(getattr(order, "pk", ""))
    )


def get_order_status_label(order) -> str:
    """Safely get the status display label for an order."""

    try:
        return order.get_status_display()
    except Exception:
        return getattr(order, "status", "-") or "-"


def format_order_detail_lines(order):
    """Format order details to human friendly chatbot response."""

    nomor_pesanan = get_order_identifier(order)
    created_at = getattr(order, "created_at", None)
    created_str = created_at.strftime("%d %b %Y %H:%M") if created_at else "-"
    shipping_method = (
        getattr(order, "selected_service_name", "")
        or getattr(order, "shipping_method", "")
        or "-"
    )

    courier_name = "-"
    if getattr(order, "shipping_provider", ""):
        try:
            courier_name = order.get_shipping_provider_display()
        except Exception:
            courier_name = order.shipping_provider
    elif getattr(order, "selected_courier", ""):
        courier_name = order.selected_courier

    tracking_number = getattr(order, "tracking_number", "") or "-"
    payment_method = (
        getattr(order, "payment_method_display", "")
        or getattr(order, "payment_method", "")
        or "-"
    )

    return [
        "Berikut detail pesanan kamu:",
        f"- No. Pesanan: {nomor_pesanan}",
        f"- Tanggal Pesanan: {created_str}",
        f"- Status: {get_order_status_label(order)}",
        f"- Jenis Pengiriman: {shipping_method}",
        f"- Kurir: {courier_name}",
        f"- No. Resi: {tracking_number}",
        f"- Metode Pembayaran: {payment_method}",
    ]


@require_POST
def chatbot_view(request):
    """Endpoint chatbot hybrid (AI + data Order)."""

    try:
        message = (request.POST.get("message") or "").strip()
        if not message:
            return JsonResponse({"reply": "Silakan tulis pertanyaanmu dulu ya 😊"})

        normalized_message = message.lower()
        user_authenticated = request.user.is_authenticated
        ai_product_safety = (
            "Jangan pernah mengarang daftar produk. Jika user meminta produk tapi intent produk gagal diproses, jawab:\n"
            "'Silakan cek halaman Produk di website Kaloriz untuk daftar terbaru'.\n"
            "Jangan pernah mengarang daftar pesanan / riwayat order. Jika user bertanya daftar pesanan tapi intent di backend gagal, jawab singkat: 'Silakan buka menu Pesanan Saya di website Kaloriz untuk melihat riwayat lengkap.'"
            "\nJika user bertanya jam operasional atau jam buka, backend sudah meng-handle, jadi jangan jawab lagi."
        )
        if any(phrase in normalized_message for phrase in ("cara pesan", "cara pemesanan", "cara order")):
            # Intent "cara pesan": balas manual tanpa memanggil AI
            return JsonResponse(
                {
                    "reply": (
                        "\n".join(
                            [
                                "Berikut cara pemesanan di Kaloriz:",
                                "1) Pilih produk dan klik Tambah ke Keranjang.",
                                "2) Buka keranjang dan cek ulang pesanan.",
                                "3) Klik Checkout, isi alamat, pilih metode pembayaran.",
                                "4) Selesaikan pembayaran, dan pesanan akan kami proses. 🙂",
                            ]
                        )
                    )
                }
            )

        operational_phrases = (
            "jam operasional",
            "jam buka",
            "buka jam berapa",
            "jam kerja",
            "jadwal buka",
        )
        if any(phrase in normalized_message for phrase in operational_phrases):
            reply = (
                "Jam operasional Kaloriz:\n"
                "- Senin – Jumat: 08.00 – 20.00\n"
                "- Sabtu: 09.00 – 18.00\n"
                "- Minggu: 10.00 – 16.00\n"
                "Di luar jam tersebut kamu tetap bisa pesan, tapi akan diproses di jam operasional ya."
            )
            return JsonResponse({"reply": reply})

        tanggal_reply = jawab_tanggal(message)
        if tanggal_reply:
            return JsonResponse({"reply": tanggal_reply})

        # Intent: daftar pesanan (tanpa AI, pakai data Order user)
        order_history_phrases = (
            "daftar pesanan",
            "pesanan saya",
            "order saya",
            "riwayat pesanan",
        )
        if any(phrase in normalized_message for phrase in order_history_phrases):
            if not user_authenticated:
                return JsonResponse(
                    {
                        "reply": (
                            "Untuk melihat daftar pesanan, silakan login terlebih dahulu ya 🙂"
                        )
                    }
                )

            orders = (
                Order.objects.filter(user=request.user)
                .order_by("-created_at")[:5]
            )

            if not orders:
                return JsonResponse(
                    {
                        "reply": (
                            "Kamu belum memiliki pesanan di Kaloriz. "
                            "Yuk coba checkout produk pertama kamu! 😊"
                        )
                    }
                )

            lines = ["Berikut 5 pesanan terakhir kamu:"]
            for idx, order in enumerate(orders, start=1):
                created_at = order.created_at
                month_name = MONTH_NAMES.get(created_at.month, "")[:3]
                tanggal_str = f"{created_at.day:02d} {month_name} {created_at.year}"
                nomor_pesanan = get_order_identifier(order)
                status_display = get_order_status_label(order)
                lines.append(
                    f"{idx}. {nomor_pesanan} – {tanggal_str} – {status_display}"
                )

            lines.append(
                "Kamu bisa melihat detail lengkap di halaman 'Pesanan Saya' di website Kaloriz."
            )

            return JsonResponse({"reply": "\n".join(lines)})

        # Intent: Lacak Pesanan (prioritas sebelum memanggil AI)
        track_order_phrases = (
            "lacak pesanan",
            "cek pesanan",
            "tracking pesanan",
            "status pesanan",
            "lacak order",
            "cek order",
            "status order",
            "tracking order",
        )

        chatbot_state = request.session.get("chatbot_state")
        last_order_ids = request.session.get("chatbot_last_orders") or []
        awaiting_order_selection = chatbot_state == "awaiting_order_selection"
        looks_like_order_reference = bool(
            re.match(r"(?i)^(ord|inv)[\w-]+$", normalized_message.replace(" ", ""))
        )
        is_track_order_intent = any(
            phrase in normalized_message for phrase in track_order_phrases
        ) or awaiting_order_selection or looks_like_order_reference

        def reset_order_session():
            request.session.pop("chatbot_state", None)
            request.session.pop("chatbot_last_orders", None)

        if is_track_order_intent:
            if not user_authenticated:
                reset_order_session()
                return JsonResponse(
                    {
                        "reply": (
                            "Untuk melacak pesanan, silakan login terlebih dahulu ya 🙂"
                        )
                    }
                )

            orders_qs = Order.objects.filter(user=request.user).order_by("-created_at")
            if not orders_qs.exists():
                reset_order_session()
                return JsonResponse(
                    {
                        "reply": (
                            "Kamu belum memiliki pesanan di Kaloriz. "
                            "Yuk coba checkout produk pertama kamu! 😊"
                        )
                    }
                )

            last_orders = list(orders_qs[:3])

            def find_order_by_reference(reference: str):
                cleaned_ref = (reference or "").strip()
                if not cleaned_ref:
                    return None

                candidate = orders_qs.filter(
                    Q(order_number__iexact=cleaned_ref)
                    | Q(midtrans_order_id__iexact=cleaned_ref)
                ).first()

                if candidate:
                    return candidate

                if cleaned_ref.isdigit():
                    try:
                        return orders_qs.filter(pk=int(cleaned_ref)).first()
                    except (TypeError, ValueError):
                        return None

                return None

            if awaiting_order_selection and not any(
                phrase in normalized_message for phrase in track_order_phrases
            ):
                selection = message.strip()
                selected_order = None

                if selection.isdigit() and last_order_ids:
                    index = int(selection) - 1
                    if 0 <= index < len(last_order_ids):
                        order_id = last_order_ids[index]
                        selected_order = next(
                            (o for o in last_orders if o.id == order_id), None
                        ) or orders_qs.filter(id=order_id).first()

                if selected_order is None:
                    selected_order = find_order_by_reference(selection)

                if selected_order is None:
                    return JsonResponse(
                        {
                            "reply": (
                                "Maaf, aku belum menemukan nomor pesanan tersebut. "
                                "Ketik 1/2/3 atau masukkan nomor pesanan lengkap ya."
                            )
                        }
                    )

                reset_order_session()
                return JsonResponse(
                    {"reply": "\n".join(format_order_detail_lines(selected_order))}
                )

            if looks_like_order_reference and not awaiting_order_selection:
                direct_order = find_order_by_reference(message)
                if direct_order:
                    reset_order_session()
                    return JsonResponse(
                        {"reply": "\n".join(format_order_detail_lines(direct_order))}
                    )

                return JsonResponse(
                    {
                        "reply": (
                            "Maaf, nomor pesanan tersebut belum ditemukan. "
                            "Pastikan formatnya benar atau ketik 'lacak pesanan' untuk melihat daftar terbaru."
                        )
                    }
                )

            request.session["chatbot_state"] = "awaiting_order_selection"
            request.session["chatbot_last_orders"] = [order.id for order in last_orders]

            lines = ["Berikut 3 pesanan terakhir kamu:"]
            for idx, order in enumerate(last_orders, start=1):
                created_at = getattr(order, "created_at", None)
                tanggal_str = created_at.strftime("%d %b %Y") if created_at else "-"
                status_display = get_order_status_label(order)
                nomor_pesanan = get_order_identifier(order)
                lines.append(
                    f"{idx}. {nomor_pesanan} – {tanggal_str} – {status_display}"
                )

            lines.append("")
            lines.append(
                "Silakan ketik angka 1 / 2 / 3 atau masukkan nomor pesanan kamu ya."
            )

            return JsonResponse({"reply": "\n".join(lines)})

        intent = classify_intent(message)
        reply_text = ""

        product_phrases = (
            "daftar produk yang tersedia",
            "produk apa saja",
            "lihat produk",
            "produk tersedia",
        )
        is_product_intent = intent == "PRODUCT_INFO" or any(
            phrase in normalized_message for phrase in product_phrases
        )

        if is_product_intent:
            # Blok intent daftar produk: query langsung database tanpa AI
            products = (
                Product.objects.filter(is_active=True, stock__gt=0)
                .order_by("name")[:10]
            )

            if not products.exists():
                return JsonResponse(
                    {
                        "reply": (
                            "Saat ini belum ada produk yang aktif di Kaloriz. "
                            "Silakan cek kembali nanti ya 😊"
                        )
                    }
                )

            lines = ["Berikut beberapa produk yang saat ini tersedia di Kaloriz:"]
            for product in products:
                lines.append(
                    f"- {product.name} – {format_currency(product.price)}"
                )
            lines.append(
                "Silakan cek halaman katalog untuk detail lengkap 😊"
            )

            return JsonResponse({"reply": "\n".join(lines)})

        if intent == "DATETIME":
            tanggal_info = format_datetime_id()
            reply_text = (
                f"Hari ini adalah {tanggal_info['tanggal_lengkap']}\n"
                f"Sekarang tanggal {tanggal_info['tanggal']} dan hari {tanggal_info['hari']}"
            )

        elif intent == "TRACK_ORDER":
            if not user_authenticated:
                reply_text = "Untuk melacak pesanan, silakan login terlebih dahulu ya 🙂"
            else:
                orders = (
                    Order.objects.filter(user=request.user)
                    .order_by("-created_at")[:3]
                )
                if not orders:
                    reply_text = "Kamu belum punya pesanan di Kaloriz 😊"
                else:
                    lines = ["Berikut beberapa pesanan terakhirmu:"]
                    for idx, order in enumerate(orders, start=1):
                        nomor_pesanan = get_order_identifier(order)
                        tanggal_str = (
                            order.created_at.strftime("%d %b %Y")
                            if getattr(order, "created_at", None)
                            else "-"
                        )
                        status_display = get_order_status_label(order)
                        lines.append(
                            f"{idx}. {nomor_pesanan} – {tanggal_str} – {status_display}"
                        )
                    lines.append(
                        "Ketik 'lacak pesanan' atau masukkan nomor pesanan untuk detail lebih lanjut."
                    )
                    reply_text = "\n".join(lines)

        elif intent == "DISTRICT_LIST":
            districts = District.objects.filter(is_active=True).order_by("name")

            if not districts.exists():
                reply_text = (
                    "Saat ini belum ada kecamatan yang terdaftar untuk pengiriman Kaloriz. "
                    "Silakan cek kembali nanti ya 😊"
                )
            else:
                lines = ["Berikut daftar kecamatan yang saat ini sudah terdaftar di Kaloriz:\n"]

                for district in districts:
                    lines.append(
                        (
                            f"• {district.name} → Tarif Reguler {format_currency(district.reg_cost)}, "
                            f"Express {format_currency(district.exp_cost)} "
                            f"(ETA Reguler {district.eta_reg}, ETA Express {district.eta_exp})"
                        )
                    )

                lines.append(
                    "\nJika kecamatanmu belum ada, silakan hubungi admin Kaloriz ya 😊"
                )

                reply_text = "\n".join(lines)

        elif intent == "ONGKIR_INFO":
            district, best_score = get_district_from_text(message)

            if district:
                reply_text = (
                    f"Ongkir ke Kecamatan {district.name}:\n"
                    f"• Tarif Reguler: {format_currency(district.reg_cost)} (ETA {district.eta_reg})\n"
                    f"• Tarif Express: {format_currency(district.exp_cost)} (ETA {district.eta_exp})"
                )
            else:
                active_districts = District.objects.filter(is_active=True).order_by("name")

                if best_score >= 0.4:
                    reply_text = (
                        "Maaf, saya belum menemukan data ongkir untuk kecamatan itu. "
                        "Silakan cek penulisan atau pilih kecamatan yang tersedia."
                    )
                else:
                    if not active_districts.exists():
                        reply_text = "Maaf, belum ada data ongkir yang tersedia."
                    else:
                        lines = ["Berikut daftar ongkir Kaloriz:"]
                        for dist in active_districts:
                            lines.append(
                                f"- {dist.name}: {format_currency(dist.reg_cost)} (Reg) / "
                                f"{format_currency(dist.exp_cost)} (Express)"
                            )
                        reply_text = "\n".join(lines)

        elif intent == "CANCEL_ORDER_INFO":
            reply_text = (
                "Pesanan yang sudah dibayar bisa dibatalkan jika statusnya belum dikemas. "
                "Silakan hubungi admin Kaloriz atau gunakan fitur pembatalan di halaman pesanan jika tersedia."
            )

        elif intent in {"PAYMENT_INFO", "SHIPPING_INFO", "OPERATIONAL_HOURS", "CONTACT_ADMIN"}:
            context_hint = (
                "Jawab secara singkat dalam Bahasa Indonesia. "
                "Jika ada informasi harga atau kebijakan, sampaikan secara umum tanpa detail sensitif."
            )
            reply_text = ask_ai_with_priority(
                f"{context_hint}\n\n{ai_product_safety}\n\nPertanyaan: {message}"
            )

        else:
            reply_text = ask_ai_with_priority(
                f"{ai_product_safety}\n\nPertanyaan: {message}"
            )

        return JsonResponse({"reply": reply_text})

    except Exception as exc:  # Fallback aman saat ada error server
        logger.exception("Error in chatbot_view: %s", exc)
        return JsonResponse(
            {"reply": "Maaf, terjadi kesalahan sistem. Silakan coba lagi."}
        )
