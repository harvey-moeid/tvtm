# Referensi Desain: "BYGA Bot — Quant Trading Bot" Dashboard

Catatan deskriptif dari mockup yang dijadikan acuan visual/struktural untuk
dashboard tvtm. Ini bukan screenshot yang di-commit (file gambar tidak
disertakan di repo ini) — deskripsi berikut cukup rinci untuk dipakai sebagai
spesifikasi implementasi.

## Layout umum

Dark theme (navy/near-black background), sidebar kiri fixed, konten utama grid
3-kolom di bagian chart, section-section di bawahnya full width dibagi 3 kolom.

## Sidebar kiri

- Logo + nama "BYGA Bot" / tagline "Quant Trading Bot"
- Menu navigasi: Dashboard (aktif), Signals, Trade History, Performance, Settings
- List "Trading Pairs": BTCUSDT Futures (M5/M15, indikator hijau live), GOLDUSDT (M5/M15, indikator hijau live)
- Card "Bot Status": badge "RUNNING" (hijau), checklist step: Market Data ✓, Strategy Engine ✓, Signal Scanner ✓, Discord Notifier ✓, Scheduler (Cron) ✓
- Footer: versi bot "BYGA Bot v1.0.0", tagline "Trade Smarter, Not Harder"

## Header / topbar

- Dua pair aktif dengan toggle timeframe M5/M15 masing-masing (BTCUSDT Futures, GOLDUSDT)
- Indikator "Live Market" (dot hijau) + timestamp WIB
- Status koneksi Discord (badge "Connected")

## Row kartu ringkasan (6 kartu sejajar)

1. Total PnL — nilai USDT + persentase kecil di bawah (mis. +12.48 USDT, ▲2.34%)
2. Win Rate — persentase besar + pecahan (mis. 68.7%, 42/61)
3. Total Trades — angka + label periode (mis. 61, (24h))
4. Current Balance — nilai USDT + icon clipboard
5. Strategy — label saja (mis. "ICT + Volume Profile")
6. Risk Management — label saja (mis. "1-2% per trade")

## Chart utama (kolom kiri, ~70% lebar)

- Tab timeframe (1m/5m/15m/1h/4h/1D) + toggle indikator: Indicators dropdown, lalu chip ON/OFF untuk ICT, VP (Volume Profile), FVG, OB
- Header chart: nama pair · timeframe · exchange, lalu OHLC + change % candle terakhir
- Candlestick chart dengan overlay:
  - Rectangle abu-abu "Order Block" di area harga tertentu
  - Rectangle biru "FVG" (Fair Value Gap) di bawah
  - Garis putus-putus (moving average / structure line)
  - Label harga saat ini dengan waktu countdown candle berjalan (mis. "66,901.4 · 02:42")
  - Anak panah hijau menunjukkan proyeksi arah
- Volume Profile: bar horizontal (oranye = jual, biru = beli dominan) di sisi kiri DAN kanan chart, sejajar sumbu harga
- Volume Profile chart kecil (candlestick volume merah/hijau) di bawah chart utama

## Panel "Latest Signal" (kolom kanan, ~30% lebar)

- Icon koin + pair + timeframe + timestamp, badge arah ("LONG" hijau / "SHORT" merah) pojok kanan atas
- 4 kotak: Entry, SL (merah), TP1, TP2 — masing-masing dengan nilai harga
- "Confidence" — progress bar + persentase (mis. 78%)
- "Score" — pecahan dari 10 (mis. 8.2/10)
- Checklist 5 item dengan icon centang hijau, tiap item pasangan label:value:
  - Market Structure → "Uptrend"
  - Liquidity → "Liquidity Sweep"
  - FVG → "Valid"
  - Order Block → "Bullish OB"
  - Volume Profile → "Buy Imbalance"
- Tombol besar "View Details →" di bawah

## Section "Signals Overview" (kolom kiri bawah)

- Tab filter: All / BTCUSDT / GOLDUSDT
- Tabel kolom: Time, Pair, TF, Direction (badge LONG/SHORT), Entry, SL, TP1, Confidence
- ~5 baris terlihat, scrollable

## Section "Performance (Last 7 Days)" (kolom tengah bawah)

- Dropdown periode ("7D")
- Angka besar total PnL periode + persentase
- Line chart area (gradient hijau) PnL harian, sumbu X tanggal
- Tabel "Pair Performance": Pair, PnL, Win Rate, Trades — per pair (BTCUSDT Futures, GOLDUSDT)

## Section "Discord Notifications" (kolom kanan bawah)

- Header dengan badge "Connected" (dot hijau)
- Feed list, tiap item: jam, judul event ("New Signal", "Trade Closed"), detail (pair/TF/direction, Entry/SL/TP, confidence/score, atau hasil closed trade + PnL)

## Palet warna (perkiraan dari mockup)

- Background: navy sangat gelap (~#0a0e1a)
- Card/panel: sedikit lebih terang, border tipis abu-kebiruan
- Aksen hijau: sinyal LONG, profit, status positif
- Aksen merah: sinyal SHORT, SL, loss
- Aksen biru/cyan: elemen netral/interaktif (FVG, tombol, highlight)
- Aksen oranye/emas: BTC branding, Order Block, volume profile jual

## Pemetaan ke checklist implementasi

Lihat `CHECKLIST.md` bagian 5 ("Dashboard — redesign card UI") untuk daftar
tugas konkret yang menerjemahkan layout di atas ke `dashboard/index.html` +
endpoint `dashboard/functions/`.
