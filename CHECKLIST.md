# Checklist Upgrade: ICT Full Suite + Dashboard Card UI

Target akhir: engine tvtm menghasilkan sinyal selengkap referensi (lihat
`docs/reference-mockup-byga-dashboard.md`) — Market Structure, Liquidity Sweep,
FVG, Order Block, Volume Profile — dan dashboard tampil sebagai card-based UI
(bukan cuma tabel) dengan chart overlay ICT.

Status: `[ ]` belum, `[x]` selesai, `[~]` sedang dikerjakan.

## 1. Engine — deteksi konsep ICT tambahan  ✅ SELESAI

- [x] `src/structure/fvg.py` — detektor Fair Value Gap (bullish & bearish, 3-candle imbalance) + mitigasi
- [x] `src/structure/order_block.py` — detektor Order Block (bullish & bearish, candle terakhir sebelum impulsive move) + mitigasi
- [x] `src/strategy/liquidity.py` — deteksi liquidity sweep (equal highs/lows, stop hunt wick)
- [x] `src/strategy/volume_profile.py` — volume per price-level (bucket), POC, buy/sell imbalance
- [x] `src/models.py` — dataclass `FairValueGap`, `OrderBlock`, `LiquiditySweep`, `VolumeProfileLevel`, `VolumeProfileResult`, `ScoreComponent`, `ScoreResult`; `Signal` + field `confidence_pct`/`score`/`checklist`
- [x] `src/config/strategy.json` — parameter baru: `fvgMinGapPct`, `obLookback`, `liquidityEqualTolerancePct`, `volumeProfileBucketCount`, `minScoreToNotify`

## 2. Engine — scoring & confidence  ✅ SELESAI

- [x] `src/strategy/scorer.py` — gabungkan 5 komponen (Market Structure 2.5, Order Block 2.5, FVG 2.0, Liquidity 1.5, Volume Profile 1.5 — total bobot 10) jadi `score` (0–10), `confidence_pct` (0–100), dan checklist per-komponen
- [x] Wired ke `src/strategy/trigger_m5.py`: FVG/OB/Liquidity/Volume Profile dihitung dari `m5_candles`, sinyal di bawah `minScoreToNotify` (default 0.0 = tidak memfilter) dibatalkan
- [ ] Validasi bobot komponen scorer lewat backtest (belum, prioritas di bagian 6)

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
- [ ] Panel "Latest Signal" kanan: arah (LONG/SHORT), Entry/SL/TP1/TP2, confidence bar, checklist 5 komponen (sudah tersedia dari `signal.checklist`), tombol "View Details"
- [ ] Section "Signals Overview" — tabel ringkas (sudah ada sebagian, perlu kolom confidence)
- [ ] Section "Performance (Last 7 Days)" — line chart PnL + tabel Pair Performance (PnL/Win Rate/Trades per pair)
- [ ] Section "Discord Notifications" — feed realtime dari tabel `signals`/`trades` terbaru
- [ ] Sidebar kiri: navigasi (Dashboard/Signals/Trade History/Performance/Settings), daftar Trading Pairs, panel "Bot Status" (checklist step pipeline: Market Data, Strategy Engine, Signal Scanner, Discord Notifier, Scheduler)
- [ ] Endpoint API baru di `dashboard/functions/`: `/api/stats` (PnL, win rate, balance), `/api/trades`, `/api/performance`

## 6. Backtest & validasi

- [ ] Backtest FVG/OB/Volume Profile/scorer terhadap data historis sebelum dipakai production (parameter & bobot belum di-lock, sama seperti komponen ICT lain di repo ini)
- [ ] Tambah unit test untuk tiap detektor baru (ikuti pola `tests/` yang sudah ada, target tetap tanpa jaringan / pakai data candle sintetis)

---

*Referensi visual: lihat `docs/reference-mockup-byga-dashboard.md`.*
