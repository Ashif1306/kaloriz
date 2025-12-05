# Kaloriz Chatbot (Asisten Kaloriz)

Fitur chatbot hybrid untuk situs e-commerce Kaloriz berbasis Django.

## Arsitektur alur data
1. **Frontend Chat Widget** mengirim teks pengguna ke endpoint `/chatbot/` via `fetch` POST.
2. **Endpoint /chatbot/** memvalidasi input dan memanggil `classify_intent()`.
3. **Intent Classifier** memutuskan apakah perlu query database `Order` atau dilempar ke AI.
4. **Order Query / Logic Intent** menangani intent khusus (misalnya lacak pesanan, panduan pembatalan).
5. **AI Responder** memakai `ask_ai_with_priority()` yang memanggil OpenRouter dengan daftar prioritas model.
6. **Response JSON** dikirim kembali ke widget, lalu ditampilkan sebagai bubble bot di UI.

## Setup environment
Buat file `.env` di root proyek (selevel `manage.py`) dengan isi dasar berikut:

```
OPENROUTER_API_KEY=<contoh_placeholder_key>
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
NOVA_MODEL_ID=<openrouter_model_id_nova_2_lite_free>
TRINITY_MODEL_ID=<openrouter_model_id_trinity_mini_free>
DEEPSEEK_MODEL_ID=<openrouter_model_id_deepseek_r1t2_chimera_free>
NEMOTRON_MODEL_ID=<openrouter_model_id_nemotron_nano_12b_2_vl_free>
```

- Ganti nilai `*_MODEL_ID` sesuai ID model OpenRouter pada akun Anda.
- `OPENROUTER_API_KEY` bisa menggunakan API key gratis dari OpenRouter.

## Konfigurasi settings
`kaloriz/settings.py` sudah memuat variabel berikut melalui `python-dotenv`:

- `OPENROUTER_API_KEY`
- `OPENROUTER_BASE_URL`
- `NOVA_MODEL_ID`
- `TRINITY_MODEL_ID`
- `DEEPSEEK_MODEL_ID`
- `NEMOTRON_MODEL_ID`
- `CHATBOT_MODELS_PRIORITY` (list urutan fallback model)

Contoh akses di kode lain:

```python
from django.conf import settings

api_key = settings.OPENROUTER_API_KEY
models_priority = settings.CHATBOT_MODELS_PRIORITY
```

## Menjalankan server & uji endpoint
1. Install dependensi: `pip install -r requirements.txt`
2. Jalankan server Django: `python manage.py runserver`
3. Uji endpoint chatbot (user harus login di sesi aktif atau gunakan token session):

```bash
curl -X POST \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -b "sessionid=<session_cookie>" \
  -d "message=Halo, bagaimana cara pemesanan?" \
  http://localhost:8000/chatbot/
```

Respons contoh:

```json
{"reply": "Halo! Kamu bisa memesan langsung di situs Kaloriz ..."}
```

## Catatan
- Chat widget contoh tersedia di `templates/base.html` (floating di kanan bawah).
- App Django baru berada di folder `ai_chatbot/` dan telah ditambahkan ke `INSTALLED_APPS` serta routing `chatbot/`.
