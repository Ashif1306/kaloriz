"""
Client util untuk berkomunikasi dengan OpenRouter menggunakan prioritas model.
"""

import logging
import re
from typing import Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# Menjamin AI menjawab tanpa markdown (instruksi sistem)
PLAIN_TEXT_INSTRUCTION = (
    "Selalu jawab dalam teks biasa tanpa markdown. Jangan gunakan bold, heading, bullet, atau kode. "
    "Gunakan kalimat biasa saja."
)


def call_openrouter(message: str, model_id: str) -> Optional[str]:
    """
    Memanggil API OpenRouter untuk menghasilkan respons chatbot.

    Mengembalikan konten teks dari pilihan pertama jika berhasil, atau None jika gagal.
    """

    url = f"{settings.OPENROUTER_BASE_URL.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model_id,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Kamu adalah Asisten Kaloriz, chatbot resmi e-commerce Kaloriz. "
                    "Gunakan Bahasa Indonesia yang ramah, sopan, dan ringkas. Jawab hanya hal terkait Kaloriz: "
                    "cara pemesanan, pembayaran, pengiriman dan ongkir, jam operasional, produk & menu, promo & "
                    "diskon, serta bantuan pelanggan. Jika user bertanya di luar konteks Kaloriz (misalnya politik, "
                    "agama, topik sensitif lain), jawab dengan sopan bahwa kamu hanya bisa membantu seputar Kaloriz. "
                    f"{PLAIN_TEXT_INSTRUCTION}"
                ),
            },
            {"role": "user", "content": message},
        ],
        "max_tokens": 400,
        "temperature": 0.4,
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=8)
        if not response.ok:
            logger.error(
                "OpenRouter call failed: status=%s, body=%s", response.status_code, response.text
            )
            return None

        data = response.json()
        choices = data.get("choices")
        if not choices:
            logger.error("OpenRouter response missing choices: %s", data)
            return None

        message_content = choices[0].get("message", {}).get("content")
        if not message_content:
            logger.error("OpenRouter response missing message content: %s", data)
            return None

        return message_content
    except requests.RequestException as exc:
        logger.error("OpenRouter request exception for model %s: %s", model_id, exc)
        return None


def strip_basic_markdown(text: str) -> str:
    """Hapus format markdown sederhana agar balasan menjadi teks biasa."""

    cleaned = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    cleaned = re.sub(r"^[-•]\s+", "", cleaned, flags=re.MULTILINE)
    cleaned = cleaned.replace("**", "").replace("*", "").replace("`", "")
    return cleaned.strip()


def ask_ai_with_priority(message: str) -> str:
    """
    Memanggil AI dengan prioritas model. Jika model utama gagal, otomatis fallback.
    """

    for model_id in getattr(settings, "CHATBOT_MODELS_PRIORITY", []):
        if not model_id:
            continue

        reply = call_openrouter(message, model_id)
        if reply:
            return strip_basic_markdown(reply)

    return "Maaf, sistem sedang sibuk. Coba beberapa saat lagi ya. 🙏"
