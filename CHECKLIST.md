# Checklist Upgrade: ICT Full Suite + Dashboard Card UI

Target akhir: engine tvtm menghasilkan sinyal selengkap referensi (lihat
`docs/reference-mockup-byga-dashboard.md`) — Market Structure, Liquidity Sweep,
FVG, Order Block, Volume Profile — dan dashboard tampil sebagai card-based UI
(bukan cuma tabel) dengan chart overlay ICT.

Status: `[ ]` belum, `[x]` selesai, `[~]` sedang dikerjakan.

## 1. Engine — deteksi konsep ICT tambahan

- [ ] `src/structure/fvg.py` — detektor Fair Value Gap (bullish & bearish, 3-candle imbalance)
- [ ] `src/structure/order_block.py` — detektor Order Block (bullish & bearish, candle terakhir sebelum impulsive move)
- [ ] `src/strategy/liquidity.py` — deteksi liquidity sweep (equal highs/lows, stop hunt wick)
- [ ] `src/strategy/volume_profile.py` — hitung volume per price-level (bucket) dari candle window
- [ ] `src/models.py` — tambah dataclass `FairValueGap`, `OrderBlock`, `LiquiditySweep`, `VolumeProfileLevel`
- [ ] `src/config/strategy.json` — parameter baru: `fvgMinGapPct`, `obLookback`, `liquidityEqualTolerancePct`, `volumeProfileBucketCount`

## 2. Engine — scoring & confidence

- [ ] `src/strategy/scorer.py` — gabungkan 5 komponen (Market Structure, Liquidity Sweep, FVG, Order Block, Volume Profile) jadi:
  - `confidence_pct` (0–100)
  - `score` (0–10)
  - checklist per-komponen (valid/invalid + label, mis. "Bullish OB", "Buy Imbalance")
- [ ] Sinyal yang score-nya di bawah threshold (`minScoreToNotify`) tidak dikirim ke Discord

## 3. Storage (D1)

- [ ] Migrasi tabel `signals`: tambah kolom `confidence_pct`, `score`, `checklist_json`
- [ ] Tabel baru `trades` untuk tracking TP/SL hit → dipakai hitung Win Rate & Total PnL
- [ ] `scripts/migrate_d1.py` — tambahkan migrasi baru (idempotent, ikuti pola migrasi risk management yang sudah ada)

## 4. Tracker (posisi berjalan)

- [ ] `src/strategy/tracker.py` — cek sinyal aktif vs harga terkini → deteksi TP1/TP2/SL hit, tulis ke tabel `trades`
- [ ] Update Discord notifier: kirim notifikasi "Trade Closed" (hasil + PnL) selain "New Signal"

## 5. Dashboard — redesign card UI (index.html atau split ke beberapa file)

- [ ] Header: nama bot, pair aktif (BTCUSDT/GOLDUSDT) + timeframe switch (M5/M15), status Live Market, jam WIB, status Discord
- [ ] Row kartu ringkasan: Total PnL, Win Rate, Total Trades (24h), Current Balance, Strategy label, Risk Management label
- [ ] Chart utama: candlestick + overlay Order Block (rect), FVG (rect), garis liquidity — lanjutan dari `lightweight-charts` yang sudah dipakai, tambah primitive/rectangle untuk OB & FVG
- [ ] Volume Profile horizontal di sisi kanan/kiri chart
- [ ] Panel "Latest Signal" kanan: arah (LONG/SHORT), Entry/SL/TP1/TP2, confidence bar, checklist 5 komponen, tombol "View Details"
- [ ] Section "Signals Overview" — tabel ringkas (sudah ada sebagian, perlu kolom confidence)
- [ ] Section "Performance (Last 7 Days)" — line chart PnL + tabel Pair Performance (PnL/Win Rate/Trades per pair)
- [ ] Section "Discord Notifications" — feed realtime dari tabel `signals`/`trades` terbaru
- [ ] Sidebar kiri: navigasi (Dashboard/Signals/Trade History/Performance/Settings), daftar Trading Pairs, panel "Bot Status" (checklist step pipeline: Market Data, Strategy Engine, Signal Scanner, Discord Notifier, Scheduler)
- [ ] Endpoint API baru di `dashboard/functions/`: `/api/stats` (PnL, win rate, balance), `/api/trades`, `/api/performance`

## 6. Backtest & validasi

- [ ] Backtest FVG/OB/Volume Profile terhadap data historis sebelum dipakai production (parameter belum di-lock, sama seperti komponen ICT lain di repo ini)
- [ ] Tambah unit test untuk tiap detektor baru (ikuti pola `tests/` yang sudah ada, target tetap tanpa jaringan / pakai data candle sintetis)

---

*Referensi visual: lihat `docs/reference-mockup-byga-dashboard.md`.*
