# TVTM — GitHub Trading Signal Engine

Python engine untuk OKX BTC-USDT-SWAP dan XAU-USDT-SWAP.
M15 market structure -> M5 entry -> risk/scoring -> Discord -> virtual trade journal.
**Ini bukan bot penempatan order ke exchange.** PnL virtual tidak sama dengan PnL riil.

## Arsitektur GitHub-only state

- Cron: GitHub Actions check-signal.yml dengan jadwal tiap 5 menit (best effort).
- Database: GitHub JSON, branch tvtm-state, file state.json.
- GitHub Actions menulis dengan GITHUB_TOKEN (Contents: write). Semua update
  memakai sha file sebelumnya untuk mendeteksi konflik; concurrency group
  mencegah penulis workflow yang paralel.
- Dashboard tetap boleh berada di Cloudflare Pages sebagai **viewer**,
  tetapi tidak memakai R2/D1 sebagai storage ataupun scheduler.
- Repository ini PUBLIC, maka state.json di branch tvtm-state juga PUBLIC:
  jangan memasukkan webhook, API key, saldo pribadi atau rahasia apa pun.
- GitHub Contents API tidak cocok untuk ukuran data sangat besar. Sebelum
  state.json mencapai ~1 MB, siapkan segmentasi/arsip; jangan paksa reset.

## Migrasi R2 lama (hanya sekali, tidak menghapus data)

1. Run engine mencoba GitHub tvtm-state/state.json.
2. Jika belum ada, state lama dibaca dari Cloudflare R2 dengan secrets lama
   CF_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY (R2_BUCKET=tvtm-data).
3. Engine membuat branch tvtm-state jika perlu, lalu menyalin state persis
   ke GitHub dan selanjutnya menulis/membaca GitHub saja.
4. Jika R2 tidak tersedia atau format rusak, proses GAGAL TERTUTUP, tidak
   menginisialisasi database kosong atau membuang posisi/sinyal yang ada.
5. Verifikasi file state.json pada branch tvtm-state di GitHub sebelum mencabut
   R2 secrets. Backup state lama terlebih dahulu.

GitHub Actions wajib mengizinkan GITHUB_TOKEN contents:write. Workflow sudah
menyatakan permissions contents:write. Variabel otomatis: GITHUB_TOKEN,
GITHUB_REPOSITORY dan GITHUB_SHA. TVTM_STATE_BRANCH opsional, default tvtm-state.

Cloudflare Pages viewer membaca public raw GitHub dengan refresh sekitar 30 detik.
Jika API privat/dengan otentikasi dibutuhkan, set GH_STATE_TOKEN (Contents:read)
di secret Cloudflare Pages, serta GH_REPO / GH_STATE_BRANCH jika berbeda.
Secret tidak boleh diteruskan ke browser. Tombol Run Now tetap opsional
menggunakan GH_DISPATCH_TOKEN dan RUN_KEY di Cloudflare Pages.

## Operasional cron

GitHub Actions schedule bukan SLA: run dapat terlambat bahkan berjam-jam.
Engine menolak closed candle M5/M15 yang stale, histori kurang atau
gap terbaru. Sinyal Discord pending lebih tua dari 20 menit di-expire.
Penutupan posisi yang gagal dikirim ke Discord akan dicoba ulang.
TIDAK ADA jaminan semua entry M5 tertangkap apabila cron GitHub terlambat.

## Logika strategi

- Bias M15: swing, trend HH/HL atau LH/LL, fresh BOS/CHoCH. Crossing baru
  disyaratkan; breakout lama tidak lagi dihitung event baru berulang.
- Entry M5: candle closed menyentuh zona M15, pin bar atau engulfing searah
  bias. Closing price maksimal maxEntryDistanceAtr x ATR dari level zona.
- SL: struktur M15 plus ATR M5 buffer; TP1=1.5R, TP2=3R default.
- TP1 baru: tutup virtual 50 persen posisi, lalu sisanya ditutup di TP2/SL;
  parameternya tp1CloseFraction. Jika hanya ada TP1 tanpa TP2, close 100
  persen posisi di TP1. Jika SL/TP terjadi bersamaan dalam satu candle OHLC,
  SL diprioritaskan konservatif.
- Posisi yang dimigrasi tanpa field tp1_close_fraction tetap menggunakan
  model PnL lama agar catatan lama tidak dimodifikasi retroaktif.
- Maksimal 1 posisi virtual per simbol default (maxOpenTradesPerSymbol).
- Lima komponen skor: Market Structure, Liquidity Sweep, FVG, Order Block,
  Volume Profile. minScoreToNotify sementara 2.5 (butuh kalibrasi backtest).
- Confidence percentage hanyalah skor konfluensi, BUKAN peluang win-rate.
- PnL saat ini berbasis pergerakan harga dan simulasi, tanpa ukuran saldo,
  slippage, leverage, fee, funding, maupun pengisian order sungguhan.

Konfigurasi: src/config/strategy.json dan src/config/symbols.json. Instrumen
dashboard/functions/api/candles.js harus sinkron dengan symbols.json.

## Tests dan validasi

- GitHub Actions Tests menjalankan pytest dan pemeriksaan syntax Pages JS.
- GitHub Actions Backtest dapat dipicu manual untuk BTCUSDT/GOLDUSDT dan
  mengunggah artifact JSON hasil pengujian data historis.
- Unit test dan backtest sintetis TIDAK membuktikan strategi profitabel.
- Sebelum trading sungguhan: validasi expectancy net of fees, profit factor,
  max drawdown, stabilitas out-of-sample, risiko portofolio dan latency.

## Recovery

Jangan reset state saat gagal baca. Periksa GitHub Actions logs, SHA commit
branch tvtm-state, file backup, lalu restore snapshot state yang benar.
GitHub state file publik; lindungi secrets di GitHub Actions dan Pages.
