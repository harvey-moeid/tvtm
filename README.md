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

### Sumber data market (OKX)

Runner GitHub Actions berada di server AS. Dari sana Binance membalas HTTP 451 (diblokir
lokasi) dan Bybit membalas 403, jadi data candle diambil dari **OKX v5 public API**
(`okx` di `src/market/exchange_adapter.py`, `GET /api/v5/market/candles`, tanpa API key):

- `BTCUSDT` -> `BTC-USDT-SWAP` (perpetual USDT-margined; setara Binance USDT-M futures).
- `GOLDUSDT` -> `XAU-USDT-SWAP` (perpetual emas OKX). **Catatan histori**: sebelumnya
  simbol ini memakai `PAXG-USDT` (spot PAX Gold) sebagai proxy, karena pada saat itu
  OKX belum punya perpetual emas asli. OKX kemudian merilis/merename instrumen ini
  (`XAUT-USDT-SWAP` -> `XAU-USDT-SWAP`) yang menurut OKX merujuk langsung ke harga spot
  emas sebagai underlying/external price source - jadi representasi GOLDUSD/XAUUSD yang
  lebih akurat daripada proxy PAXG spot, dan sudah dipindahkan di `symbols.json`.
  **Penting untuk dashboard**: `dashboard/functions/api/candles.js` HARUS selalu
  memakai `exchange_symbol` yang SAMA PERSIS dengan `symbols.json` - keduanya sempat
  tidak sinkron (dashboard masih PAXG-USDT saat engine sudah pindah ke XAU-USDT-SWAP),
  membuat chart di dashboard menampilkan instrumen berbeda dari yang dipakai untuk
  menghasilkan sinyal.

Catatan teknis: candle OKX datang terbaru-dulu dan punya flag `confirm` (1 = closed);
adapter membalik urutannya dan hanya menganggap closed kalau `confirm=1` DAN waktunya sudah
lewat. Satuan volume beda per jenis instrumen (spot: `vol` = koin dasar; swap/perpetual:
`volCcy` = koin dasar dan `vol` = jumlah kontrak menurut dokumentasi OKX), dan adapter
menormalkannya ke koin dasar (dipakai jg oleh `src/market/history_fetch.py` untuk backtest
dan `dashboard/functions/api/candles.js` untuk chart). Limit OKX maksimal 300 candle per
panggilan endpoint live (bot butuh ~205). IP runner GitHub dipakai bersama, jadi
HTTP 429 (rate limit) sesekali mungkin terjadi; fetch sudah retry 3x dengan jeda 2 detik.

Adapter lain (`kraken_spot`, `binance_spot`, `binance_futures`) tetap terdaftar dan bisa
dipilih lewat field `exchange` di `symbols.json`.

Kalau semua market gagal mengambil data candle, `python -m src.main` keluar dengan
kode 1 sehingga run di GitHub Actions berwarna merah (sebelumnya tetap hijau dengan
"no signal generated").

## Anti-noise filter (§13 PRD)

Ada 2 threshold terpisah, karena pin bar secara definisi butuh body KECIL:

- `minEngulfingBodyRangeRatio` (default 0.35) - utk candle engulfing, body harus
  cukup besar biar bukan noise.
- `minPinBarBodyRangeRatio` (default 0.03) - utk pin bar, cuma menyaring doji murni
  (body ~0), bukan menyaring pin bar itu sendiri.

Nilai-nilai ini **belum di-lock** dan perlu tuning lewat backtest (lihat bagian
"Backtest" di bawah - tooling-nya sudah tersedia).

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
  `maxStopDistancePct`, atau R:R (`riskRewardTargets[0]`) di bawah `minRiskRewardRatio`,
  sinyal **dibatalkan** sepenuhnya - bukan cuma catatan info. **Catatan**: karena TP
  didefinisikan SEBAGAI kelipatan risiko itu sendiri, cek R:R ini pada dasarnya
  memvalidasi konfigurasi (statis, sama untuk semua sinyal dgn config yang sama), bukan
  R:R dinamis per-sinyal berdasarkan level likuiditas independen. Sebelumnya semua
  sinyal yang lolos price-action langsung dikirim apa adanya, terlepas dari apakah
  trade-nya masuk akal secara risiko.

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
dan perlu ditinjau dengan data historis riil sebelum dipakai penuh di production - lihat
bagian "Backtest" di bawah.

## Backtest

`src/backtest/` berisi walk-forward simulator yang me-replay strategi live (bias M15 ->
trigger M5 -> risk management -> scorer) candle demi candle di atas histori OKX,
**tanpa menyentuh D1/Discord asli**, buat mengestimasi win-rate/expectancy/drawdown
sebelum parameter dipakai untuk keputusan trading riil:

```bash
pip install -r requirements.txt
python scripts/backtest.py --symbol BTCUSDT --candles 6000       # ~20 hari candle M5
python scripts/backtest.py --symbol GOLDUSDT --candles 6000 --out backtest_gold.json
```

Atau lewat GitHub Actions (kalau lingkungan lokal tidak punya akses ke `www.okx.com`):
buka tab **Actions -> Backtest -> Run workflow**, isi `symbol` dan `candles`, hasilnya
diunggah sebagai artifact JSON (`backtest_result.json`, retensi 90 hari).

Yang dipakai ulang persis dari kode produksi (bukan reimplementasi terpisah, supaya
hasil backtest benar-benar merepresentasikan apa yang akan terjadi kalau strategi ini
jalan live):
- `compute_m15_bias` / `evaluate_m5_trigger` - fungsi orkestrasi yang SAMA dipakai cron.
- `src/strategy/pnl.py` (`r_multiple`, `pnl_pct`) - dipakai bersama oleh
  `src/strategy/tracker.py` (live) dan `src/backtest/simulator.py`, jadi rumus PnL
  tidak pernah diam-diam berbeda antara backtest dan live.
- Cooldown/rate-limit disimulasikan lewat `src/backtest/store.py` (`InMemorySignalStore`)
  memakai **jam simulasi** yang di-advance manual tiap candle - BUKAN wall-clock seperti
  SQL produksi (`strftime(..., 'now', ...)`), karena me-replay data berbulan-bulan lalu
  dengan wall-clock asli akan membuat `cooldownMinutes` tidak pernah aktif sama sekali.

Histori diambil lewat `src/market/history_fetch.py` (endpoint OKX `history-candles`,
paginasi mundur - beda dari `src/market/fetch_candles.py` yang dipakai cron live dan
dibatasi 300 candle/panggilan).

**Status saat ini**: engine backtest sudah dibangun dan divalidasi dengan candle
sintetis (`tests/test_backtest_*.py` - trade lewat SL/TP terhitung tepat, cooldown
terbukti mencegah duplikat, dst), tapi **belum pernah dijalankan terhadap data OKX
sungguhan** (lihat `CHECKLIST.md` §6). Menjalankannya untuk BTCUSDT & GOLDUSDT lewat
`workflow_dispatch` di atas, lalu meninjau win-rate/expectancy/drawdown hasilnya, adalah
langkah berikutnya sebelum parameter (ATR multiplier, R:R minimum, bobot scorer) dipakai
untuk keputusan trading riil.

Hasil backtest adalah **estimasi historis, bukan jaminan performa ke depan** - tidak
memperhitungkan slippage, funding rate perpetual, atau downtime API OKX/D1/Discord.

## Test suite

Repo ini menyertakan unit + integration test (`tests/`) yang mengunci perilaku setiap
modul murni (ATR, struktur, BOS/CHoCH, zona, pattern, risk management, volume filter,
cooldown/rate-limit, idempotency, scorer, backtest engine) plus integration test
end-to-end `evaluate_m5_trigger` pakai data candle sintetis dan D1 client palsu
in-memory (tidak perlu jaringan). Jalankan:

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

Modul I/O eksternal (`market/exchange_adapter.py`, `storage/d1_client.py`,
`notify/notify_discord.py`, `market/history_fetch.py`) sudah lolos syntax/import check
tapi **belum pernah dites terhadap API asli** - disarankan jalankan `workflow_dispatch`
manual sekali di GitHub Actions sebelum mengandalkannya penuh, dan pantau log run pertama.

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
4. **Backtest historis sudah ada tooling-nya** (`src/backtest/`, lihat bagian
   "Backtest" di atas) untuk memvalidasi win-rate/expectancy strategi maupun parameter
   risk management, tapi **belum pernah dijalankan terhadap data OKX sungguhan** - ini
   prioritas berikutnya sebelum sinyal dipakai untuk keputusan trading riil.
