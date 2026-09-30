# Robo Financial Advisor (standalone module, mobile portrait)

Vanilla HTML/CSS/JS + FastAPI + Gemini + CSV portfolios + lightweight RAG.

## Run
```bash
pip install -r requirements.txt
cp .env.example .env      # set GEMINI_API_KEY (backend only)
uvicorn backend.main:app --reload
# open http://localhost:8000/  (pilih profil uji -> chat)
```
Without a key the chat still works in data-only mode (deterministic answers, cards, comparison, chart).

## Integrating with your Efficient Frontier app
- `backend/risk.py::get_user_risk_profile()` is a stub (env `USER_RISK_PROFILE`, default `Moderat`). Replace with your risk engine. Descriptions/horizons for Konservatif and Agresif are placeholders.
- `backend/portfolio.py` reads the CSV (IDs generated: KON-01..AGR-05). `frontier()` returns the CSV points; swap in your existing frontier output if you have one.
- Mount `frontend/robo-advisor.html` beside your `index.html`; the API is same-origin under `/api`.

## Design notes
- Intent is detected in code; backend tools run first; Gemini only writes the explanation from that JSON. Cards, comparison tables and citations come from the backend, never from the model.
- Citations are the retrieved knowledge files, so they cannot be fabricated. Add `.md` files to `backend/data/knowledge/` to extend RAG.

## Alur chat (advice)
Tujuan -> jangka waktu -> nominal, tiap pertanyaan punya quick-chat template (`backend/advice.py::QUESTIONS`).
Setiap jawaban template menaikkan/menurunkan paket di dalam profil asli (mulai dari paket 3 dari 5, dibatasi 1-5). Jawaban di luar template = delta 0 (profil asli).
Bobot delta adalah PLACEHOLDER: validasi dengan bisnis/compliance. Nominal > Rp200 juta (atau ketikan bebas yang terbaca > 200 juta) menampilkan tombol WhatsApp RM Bahana Signature; atur nomor lewat `RM_WA_NUMBER` di `.env` (default hanya placeholder).
Halaman `index.html` = pemilih profil uji (`robo-advisor.html?profile=Moderat`). Ganti nama bila bentrok dengan index.html aplikasi Anda.
Tombol Beli membuka modal mock (tanpa transaksi nyata).

## Batas konteks
Hanya 3 giliran terakhir (6 pesan, maks 500 karakter/pesan) dikirim ke Gemini; profil, tujuan, jangka waktu, nominal, dan paket rekomendasi dikirim sebagai konteks ringkas `user_plan`.
