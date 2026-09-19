"""
Volume confluence filter (upgrade, opsional/opt-in lewat requireVolumeConfirmation).

Ide: candle trigger (retest zona + pattern valid) yang volumenya jauh di
bawah rata-rata menunjukkan partisipasi pasar lemah di titik itu - retest
tanpa minat beli/jual nyata secara empiris lebih rawan berakhir fakeout
dibanding retest yang diiringi volume di atas rata-rata (indikasi order flow
riil, bukan cuma harga "numpang lewat").

Filter ini sengaja OPT-IN (default false di strategy.json), bukan langsung
aktif, karena:
1. Ini confluence tambahan di luar cakupan price-action murni yang sudah ada,
   jadi perlu divalidasi via backtest sebelum jadi syarat wajib.
2. Kualitas data volume bisa berbeda karakteristik antar exchange/market
   (futures vs spot, crypto vs proxy emas) - lebih aman default mati dan
   dinyalakan per-symbol setelah ditinjau.
"""

from __future__ import annotations

from typing import List

from src.models import Candle


def passes_volume_filter(candles: List[Candle], cfg: dict) -> bool:
    if not cfg.get("requireVolumeConfirmation", False):
        return True

    lookback = cfg.get("volumeLookbackCandles", 20)
    multiplier = cfg.get("minVolumeMultiplier", 1.0)

    if lookback <= 0 or len(candles) < lookback + 1:
        return True

    trigger = candles[-1]
    baseline = candles[-(lookback + 1):-1]
    avg_volume = sum(c.volume for c in baseline) / len(baseline)
    if avg_volume <= 0:
        return True

    return trigger.volume >= avg_volume * multiplier
