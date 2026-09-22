"""
Volume Profile - volume dikelompokkan per price-level (bucket), bukan per
waktu seperti candle biasa. Dipakai untuk lihat di harga mana partisipasi
pasar paling besar (Point of Control / POC) dan apakah dominasi volume
condong ke sisi beli atau jual (imbalance) di window candle terakhir.

Karena data candle di repo ini (OKX REST, lihat README) tidak menyediakan
bid/ask volume terpisah, volume tiap candle diklasifikasi buy vs sell
secara proxy dari arah candle itu sendiri: candle bullish -> seluruh
volume-nya dihitung sebagai buy_volume, candle bearish -> sell_volume.
Ini pendekatan sederhana/standar dipakai banyak tool retail ketika tidak
ada order-flow/tape data asli - BUKAN volume delta yang presisi, cuma
proxy arah dominan.

Bucket dibuat dengan membagi rentang [low_terendah, high_tertinggi] dari
window candle secara merata menjadi `bucket_count` bagian (default 24,
cukup granular untuk M5/M15 tanpa terlalu berat dihitung tiap run).
Volume tiap candle didistribusikan proporsional ke tiap bucket yang
tumpang tindih dengan range [low, high] candle itu (bukan cuma ditaruh di
satu titik/close), supaya candle dengan range lebar tidak salah
menumpuk semua volume-nya di satu bucket sempit.
"""

from __future__ import annotations

from typing import List

from src.models import Candle, VolumeProfileLevel, VolumeProfileResult


def compute_volume_profile(candles: List[Candle], bucket_count: int = 24) -> VolumeProfileResult:
    if not candles or bucket_count < 1:
        return VolumeProfileResult()

    lowest = min(c.low for c in candles)
    highest = max(c.high for c in candles)
    if highest <= lowest:
        return VolumeProfileResult()

    bucket_size = (highest - lowest) / bucket_count
    buy_totals = [0.0] * bucket_count
    sell_totals = [0.0] * bucket_count

    for c in candles:
        is_buy = c.is_bullish
        # index bucket yang overlap dengan range candle ini
        start_idx = max(0, int((c.low - lowest) / bucket_size))
        end_idx = min(bucket_count - 1, int((c.high - lowest) / bucket_size))
        overlapped = list(range(start_idx, end_idx + 1)) or [start_idx]
        share = c.volume / len(overlapped)
        for idx in overlapped:
            if is_buy:
                buy_totals[idx] += share
            else:
                sell_totals[idx] += share

    levels = [
        VolumeProfileLevel(
            price_low=lowest + i * bucket_size,
            price_high=lowest + (i + 1) * bucket_size,
            buy_volume=buy_totals[i],
            sell_volume=sell_totals[i],
        )
        for i in range(bucket_count)
    ]

    poc = max(levels, key=lambda lv: lv.total_volume) if levels else None
    poc_price = poc.mid if poc and poc.total_volume > 0 else None

    total_buy = sum(buy_totals)
    total_sell = sum(sell_totals)
    total = total_buy + total_sell
    if total <= 0:
        imbalance = "neutral"
    else:
        buy_share = total_buy / total
        if buy_share >= 0.55:
            imbalance = "buy_imbalance"
        elif buy_share <= 0.45:
            imbalance = "sell_imbalance"
        else:
            imbalance = "neutral"

    return VolumeProfileResult(levels=levels, poc_price=poc_price, imbalance=imbalance)
