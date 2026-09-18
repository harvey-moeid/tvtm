# tv-alert-relay (Python)

Implementasi PRD `PRD_Notifikasi_Trading_Cron_v4.md` — full Python, dijalankan sebagai
GitHub Actions cron, tanpa Cloudflare Worker (D1 diakses langsung via REST API resmi Cloudflare).

## Arsitektur

```
GitHub Actions (cron */5 menit)
        │
        ▼
   src/main.py
        │
        ├─ fetch M15 + M5 candle (closed only) — src/market/
        ├─ hitung bias M15 (structure + swing + BOS/CHoCH) — src/structure/, src/strategy/bias_m15.py
        ├─ evaluasi trigger M5 (zona + retest + pattern + anti-noise) — src/strategy/trigger_m5.py
        ├─ idempotency + cooldown via Cloudflare D1 (REST API) — src/storage/
        └─ kirim Discord webhook — src/notify/
```

**Kenapa tanpa Worker?** Cloudflare D1 punya HTTP Query API resmi
(`POST /accounts/{id}/d1/database/{id}/query`) yang bisa dipanggil langsung pakai
API Token — jadi tidak perlu lapisan Cloudflare Worker terpisah untuk logging.
Seluruh stack aplikasi murni Python.

## Setup

1. **Buat D1 database** di Cloudflare dashboard, catat `account_id` dan `database_id`.
2. **Buat API Token** dengan permission `D1:Edit`.
3. Jalankan sekali untuk membuat tabel:
   ```bash
   pip install -r requirements.txt
   export CF_ACCOUNT_ID=...
   export CF_D1_DATABASE_ID=...
   export CF_API_TOKEN=...
   python scripts/setup_d1.py
   ```
4. Set GitHub Repository Secrets: `DISCORD_WEBHOOK_URL`, `CF_ACCOUNT_ID`,
   `CF_D1_DATABASE_ID`, `CF_API_TOKEN`.
5. Push repo ini — workflow `.github/workflows/check-signal.yml` otomatis jalan tiap 5 menit.

## Konfigurasi strategi

- `src/config/symbols.json` — daftar market + mapping simbol exchange.
- `src/config/strategy.json` — parameter tuning (swing lookback, toleransi zona,
  filter anti-noise, cooldown) dengan override per-symbol.

### ⚠️ Catatan penting soal simbol GOLDUSDT (AC-14 PRD)

Tidak ada pair asli "GOLDUSDT" di exchange manapun. Implementasi ini memakai
**`PAXGUSDT`** (PAX Gold/USDT, Binance spot) sebagai proxy — PAXG melacak harga
emas 1:1 per troy ounce. **Wajib divalidasi/diganti** dengan data provider resmi
sebelum dipakai untuk keputusan production, sesuai catatan di `symbols.json`.

## Anti-noise filter (§13 PRD)

Ada 2 threshold terpisah, karena pin bar secara definisi butuh body KECIL:

- `minEngulfingBodyRangeRatio` (default 0.35) — utk candle engulfing, body harus
  cukup besar biar bukan noise.
- `minPinBarBodyRangeRatio` (default 0.03) — utk pin bar, cuma menyaring doji murni
  (body ~0), bukan menyaring pin bar itu sendiri.

Nilai-nilai ini **belum di-lock** dan perlu tuning lewat backtest (sesuai PRD §13).

## Idempotency & Cooldown (§5 & §14 PRD)

- `signal_key` = `symbol:market:timeframe:candle_time:direction`, UNIQUE di D1.
  Insert dulu (checkpoint dedup) → baru kirim Discord → baru `UPDATE notified=1`.
  Kalau proses mati di tengah, run berikutnya retry notify tanpa membuat row baru.
- `cooldown_key` = `symbol:timeframe:zone_type:zone_level:structure_event:event_candle_time:direction`.
  Menyertakan timestamp event struktur pembentuk zona, sehingga otomatis "kadaluarsa"
  begitu ada BOS/CHoCH baru atau zona baru — sesuai syarat PRD §14.

## Menjalankan test cepat (tanpa API eksternal)

Sandbox pengembangan ini tidak punya akses ke Binance/Discord/Cloudflare, jadi
verifikasi dilakukan dengan data candle sintetis terhadap seluruh pipeline murni
(structure → bias → zone → pattern → trigger → cooldown) — semua lolos. Modul
I/O (`market/exchange_adapter.py`, `storage/d1_client.py`, `notify/notify_discord.py`)
sudah lolos syntax/import check tapi **belum pernah dites terhadap API asli** —
disarankan jalankan `workflow_dispatch` manual sekali di GitHub Actions sebelum
mengandalkannya penuh, dan pantau log run pertama.

## Struktur decision yang perlu diperhatikan reviewer

1. **BOS vs CHoCH**: breakout searah trend berjalan = BOS, berlawanan = CHoCH,
   pakai `close` (bukan wick) sebagai ambang breakout (§9, implementasi di
   `src/structure/bos_choch.py`).
2. **M15 bias dihitung ulang setiap run** (tiap 5 menit), bukan cuma tiap 15 menit —
   lebih sederhana secara scheduling dan tetap akurat karena candle M15 yang belum
   close otomatis diabaikan oleh `fetch_closed_candles`.
3. Evaluasi standalone M15 (§10 poin d PRD) belum diimplementasikan sebagai notifikasi
   terpisah — flag `standaloneM15Signals` di `strategy.json` disediakan sebagai
   placeholder untuk pengembangan lanjutan.
