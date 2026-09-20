# tv-alert-relay (Python)

Implementasi PRD `PRD_Notifikasi_Trading_Cron_v4.md` - full Python, dijalankan sebagai
GitHub Actions cron, tanpa Cloudflare Worker (D1 diakses langsung via REST API resmi Cloudflare).

## Arsitektur

```
GitHub Actions (cron */5 menit)
        |
        v
   src/main.py
        |
        +- fetch M15 + M5 candle (closed only)              -> src/market/
        +- hitung bias M15 (structure + swing + BOS/CHoCH)   -> src/structure/, src/strategy/bias_m15.py
        +- evaluasi trigger M5 (zona + retest + pattern +
           anti-noise + volume + RISK MANAGEMENT)            -> src/strategy/trigger_m5.py
        +- idempotency + cooldown + rate-limit via D1         -> src/storage/, src/strategy/cooldown.py
        +- kirim Discord webhook (+ SL/TP/R:R)                -> src/notify/
```

**Kenapa tanpa Worker?** Cloudflare D1 punya HTTP Query API resmi
(`POST /accounts/{id}/d1/database/{id}/query`) yang bisa dipanggil langsung pakai
API Token - jadi tidak perlu lapisan Cloudflare Worker terpisah untuk logging.
Seluruh stack aplikasi murni Python.

## Setup

1. **Buat D1 database** di Cloudflare dashboard, catat `account_id` dan `database_id`.
2. **Buat API Token** dengan permission `D1:Edit`.
3. Jalankan sekali untuk membuat tabel (instalasi baru):
   ```bash
   pip install -r requirements.txt
   export CF_ACCOUNT_ID=...
   export CF_D1_DATABASE_ID=...
   export CF_API_TOKEN=...
   python scripts/setup_d1.py
   ```
   Kalau database sudah ada dari SEBELUM upgrade risk management ini, jalankan
   migrasi (aman diulang, lihat bagian "Upgrade strategi inti" di bawah):
   ```bash
   python scripts/migrate_d1.py
   ```
4. Set GitHub Repository Secrets: `DISCORD_WEBHOOK_URL`, `CF_ACCOUNT_ID`,
   `CF_D1_DATABASE_ID`, `CF_API_TOKEN`.
5. Push repo ini -> workflow `.github/workflows/check-signal.yml` otomatis jalan tiap 5 menit.

## Konfigurasi strategi

- `src/config/symbols.json` - daftar market + mapping simbol exchange.
- `src/config/strategy.json` - parameter tuning dengan override per-symbol.

### Sumber data market (Kraken)

Runner GitHub Actions berada di server AS, dan Binance membalas HTTP 451 (diblokir
lokasi) ke IP tersebut, jadi data candle diambil dari **Kraken spot**
(`kraken_spot` di `src/market/exchange_adapter.py`, endpoint publik `/0/public/OHLC`):

- `BTCUSDT` -> pair Kraken `XBTUSD` (BTC/USD, spot; sebelumnya Binance USDT-M futures).
- `GOLDUSDT` -> pair Kraken `PAXGUSD` (PAX Gold/USD, spot).

Harga dalam **USD**, bukan USDT; label `BTCUSDT`/`GOLDUSDT` dipertahankan supaya
override di `strategy.json` dan data di D1 tetap konsisten. Kraken hanya membuat
candle kalau ada transaksi, jadi gap ditambal candle datar (volume 0); ini relevan
kalau `requireVolumeConfirmation` diaktifkan, terutama untuk PAXG yang likuiditasnya tipis.

Kalau semua market gagal mengambil data candle, `python -m src.main` keluar dengan
kode 1 sehingga run di GitHub Actions berwarna merah (sebelumnya tetap hijau dengan
"no signal generated").

### Catatan penting soal simbol GOLDUSDT (AC-14 PRD)

Tidak ada pair asli "GOLDUSDT" di exchange manapun. Implementasi ini memakai
**PAX Gold (PAXG)** sebagai proxy - PAXG melacak harga emas 1:1 per troy ounce.
**Wajib divalidasi/diganti** dengan data provider resmi sebelum dipakai untuk
keputusan production, sesuai catatan di `symbols.json`.

## Anti-noise filter (§13 PRD)

Ada 2 threshold terpisah, karena pin bar secara definisi butuh body KECIL:

- `minEngulfingBodyRangeRatio` (default 0.35) - utk candle engulfing, body harus
  cukup besar biar bukan noise.
- `minPinBarBodyRangeRatio` (default 0.03) - utk pin bar, cuma menyaring doji murni
  (body ~0), bukan menyaring pin bar itu sendiri.

Nilai-nilai ini **belum di-lock** dan perlu tuning lewat backtest.

## Idempotency & Cooldown (§5 & §14 PRD)

- `signal_key` = `symbol:market:timeframe:candle_time:direction`, UNIQUE di D1.
  Insert dulu (checkpoint dedup) -> baru kirim Discord -> baru `UPDATE notified=1`.
  Kalau proses mati di tengah, run berikutnya retry notify tanpa membuat row baru.
- `cooldown_key` = `symbol:timeframe:zone_type:zone_level:structure_event:event_candle_time:direction`.
  Menyertakan timestamp event struktur pembentuk zona, sehingga otomatis "kadaluarsa"
  begitu ada BOS/CHoCH baru atau zona baru.
- `cooldownMinutes` (§14) kini benar-benar aktif sebagai rate-limit tambahan berbasis
  waktu murni per symbol+timeframe+direction (lihat bagian upgrade di bawah).

---

## Upgrade strategi inti

Upgrade ini menutup kekosongan terbesar versi awal (tidak ada manajemen risiko sama
sekali) dan mengurangi beberapa sumber sinyal palsu/whipsaw. **Semua parameter baru
punya default yang aman-mundur (backward compatible)** kecuali `requireRiskManagement`
yang sengaja default `true` karena itu inti dari upgrade ini.

### 1. Risk management (SL/TP/R:R) - `src/strategy/risk.py`

Sebelumnya sistem hanya mengirim arah (BUY/SELL) tanpa level eksekusi maupun ukuran
risiko sama sekali. Sekarang tiap sinyal (kalau `requireRiskManagement: true`, default)
membawa:

- **Stop Loss**: di luar level zona (swing yang memicu sinyal) + buffer ATR M5, supaya
  invalidation point bermakna secara price-action, bukan jarak arbitrer, dan tidak
  persis di garis swing yang gampang kena stop-hunt/noise wick.
- **Take Profit 1 & 2**: kelipatan R (`riskRewardTargets`, default `[1.5, 3.0]`) dari
  risiko aktual.
- **Filter kelayakan risiko**: kalau jarak SL di luar `minStopDistancePct`/
  `maxStopDistancePct`, atau R:R di bawah `minRiskRewardRatio`, sinyal **dibatalkan**
  sepenuhnya - bukan cuma catatan info. Sebelumnya semua sinyal yang lolos price-action
  langsung dikirim apa adanya, terlepas dari apakah trade-nya masuk akal secara risiko.

Set `requireRiskManagement: false` di `strategy.json` untuk kembali ke perilaku lama
(sinyal arah saja, tanpa SL/TP) kalau diperlukan.

### 2. Toleransi zona adaptif terhadap volatilitas (ATR) - `src/strategy/zones.py`

`zoneTolerancePct` lama itu statis per-symbol dan gampang basi ketika rezim volatilitas
berubah. Sekarang toleransi dihitung `max(zoneTolerancePctFloor, ATR_M15 * zoneAtrMultiplier / level * 100)`
- otomatis melebar saat market volatile, menyempit saat tenang. Set `zoneAtrMultiplier: 0`
untuk kembali ke toleransi statis murni.

### 3. Konfirmasi struktur lebih ketat - `src/structure/market_structure.py`

`minStructureConfirmation` (default `1`, identik perilaku lama) menentukan berapa
banyak swing high/low berturut-turut yang harus konsisten sebelum trend dianggap
UP/DOWN. Menaikkannya membuat sistem jatuh ke RANGE (tidak yakin/no-trade) saat ada
swing "shakeout", alih-alih salah membaca sebagai reversal - gagal ke "tidak trading"
jauh lebih aman daripada gagal ke "arah salah".

### 4. Buffer breakout minimum - `src/structure/bos_choch.py`

`structureBreakBufferPct` (default `0.05`) mensyaratkan `close` menembus level swing
lebih jauh dari sekadar marginal, menyaring BOS/CHoCH palsu dari noise close yang cuma
"numpang lewat" tipis di atas/bawah level.

### 5. Filter volume (opsional, opt-in) - `src/strategy/volume_filter.py`

`requireVolumeConfirmation` (default `false`) menyaring retest dengan volume di bawah
rata-rata `volumeLookbackCandles` x `minVolumeMultiplier` - indikasi partisipasi pasar
lemah di titik retest. Default mati karena ini confluence tambahan di luar price-action
murni dan perlu ditinjau/divalidasi per-symbol dulu sebelum diaktifkan.

### 6. `cooldownMinutes` sekarang benar-benar aktif - `src/strategy/cooldown.py`

Versi awal punya parameter ini di `strategy.json` tapi **tidak pernah dipakai di kode**
(diakui eksplisit di docstring versi awal). Sekarang ada layer `is_rate_limited()`
terpisah: walau setup struktural berbeda (zona/event baru, sehingga `cooldown_key` ikut
beda), tetap ada jeda minimum antar notifikasi untuk symbol+timeframe+arah yang sama -
mencegah spam saat market membentuk banyak BOS/CHoCH kecil berturut-turut dalam waktu
singkat. Set `cooldownMinutes: 0` untuk mematikan layer ini.

### Migrasi database untuk instalasi yang sudah ada

Kolom baru (`stop_loss`, `take_profit_1/2`, `risk_reward_1/2`, `atr`,
`zone_tolerance_pct_used`) perlu ditambahkan ke tabel `signals` yang sudah ada:

```bash
python scripts/migrate_d1.py
```

Aman dipanggil berkali-kali (idempotent, mengecek `PRAGMA table_info` dulu). **Jangan**
jalankan `sql/migrations/0002_risk_management.sql` secara manual berulang - SQLite/D1
tidak mendukung `ADD COLUMN IF NOT EXISTS` dan akan error di run kedua.

### Parameter baru di `strategy.json`

| Parameter | Default | Fungsi |
|---|---|---|
| `atrPeriod` | 14 | Periode ATR (Wilder) untuk M15 & M5 |
| `requireRiskManagement` | true | Wajib SL/TP/RR layak, atau sinyal dibatalkan |
| `slAtrBufferMultiplier` | 0.25 | Buffer SL = ATR M5 x nilai ini, di luar level zona |
| `riskRewardTargets` | [1.5, 3.0] | Target TP1/TP2 dalam kelipatan R |
| `minRiskRewardRatio` | 1.2 | R:R minimum TP1 supaya sinyal dianggap layak |
| `minStopDistancePct` / `maxStopDistancePct` | 0.05 / 5.0 | Batas wajar jarak SL (% dari entry) |
| `zoneTolerancePctFloor` | 0.05 | Lantai minimum toleransi zona adaptif |
| `zoneAtrMultiplier` | 0.5 | Skala toleransi zona terhadap ATR M15 (0 = pakai statis) |
| `minStructureConfirmation` | 1 | Jumlah pasangan swing berturut-turut utk konfirmasi trend |
| `structureBreakBufferPct` | 0.05 | Buffer breakout minimum (% dari level swing) |
| `requireVolumeConfirmation` | false | Aktifkan filter konfluensi volume |
| `volumeLookbackCandles` / `minVolumeMultiplier` | 20 / 1.0 | Parameter filter volume |

**Semua nilai default di atas belum divalidasi backtest** (sama seperti parameter lama)
dan perlu ditinjau dengan data historis riil sebelum dipakai penuh di production.

## Test suite

Upgrade ini menyertakan unit + integration test (79 test, `tests/`) yang mengunci
perilaku setiap modul murni (ATR, struktur, BOS/CHoCH, zona, pattern, risk management,
volume filter, cooldown/rate-limit, idempotency) plus 1 integration test end-to-end
`evaluate_m5_trigger` pakai data candle sintetis dan D1 client palsu in-memory (tidak
perlu jaringan). Jalankan:

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

Modul I/O eksternal (`market/exchange_adapter.py`, `storage/d1_client.py`,
`notify/notify_discord.py`) sudah lolos syntax/import check tapi **belum pernah dites
terhadap API asli** - disarankan jalankan `workflow_dispatch` manual sekali di GitHub
Actions sebelum mengandalkannya penuh, dan pantau log run pertama.

## Struktur decision yang perlu diperhatikan reviewer

1. **BOS vs CHoCH**: breakout searah trend berjalan = BOS, berlawanan = CHoCH,
   pakai `close` (bukan wick) sebagai ambang breakout, ditambah buffer minimum
   (`src/structure/bos_choch.py`).
2. **M15 bias dihitung ulang setiap run** (tiap 5 menit), bukan cuma tiap 15 menit -
   lebih sederhana secara scheduling dan tetap akurat karena candle M15 yang belum
   close otomatis diabaikan oleh `fetch_closed_candles`.
3. Evaluasi standalone M15 (§10 poin d PRD) belum diimplementasikan sebagai notifikasi
   terpisah - flag `standaloneM15Signals` di `strategy.json` disediakan sebagai
   placeholder untuk pengembangan lanjutan.
4. **Belum ada backtest historis** untuk memvalidasi win-rate/expectancy strategi
   maupun parameter risk management baru - ini prioritas berikutnya sebelum sinyal
   dipakai untuk keputusan trading riil.
