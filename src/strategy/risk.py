"""
Risk management: stop-loss, take-profit multi-target, dan filter kelayakan
risk:reward. Ini mengisi kekosongan terbesar di versi awal strategi -
sebelumnya sistem hanya menghasilkan sinyal arah (BUY/SELL) tanpa level
eksekusi maupun ukuran risiko sama sekali.

Filosofi:
- Stop Loss ditempatkan berbasis STRUKTUR (di luar level zona/swing yang
  memicu sinyal), bukan jarak arbitrer - kalau level itu tertembus, premis
  price-action di balik sinyal ini sudah gugur, jadi itu invalidation point
  yang bermakna, bukan sekadar "N pip dari entry".
- Buffer tambahan berbasis ATR (bukan angka tetap) ditambahkan di luar level
  struktur tsb, supaya SL tidak persis di garis swing yang gampang kena
  stop-hunt/noise wick, dan buffer ini otomatis menyesuaikan volatilitas
  saat ini alih-alih nilai statis yang cepat basi.
- Take Profit dihitung sebagai kelipatan R (risk-based multiple) dari risiko
  aktual, bukan level likuiditas lawan yang belum tentu valid - lebih
  konsisten dan mudah dituning/divalidasi lewat backtest.
- Kalau risiko (jarak SL) di luar batas wajar (terlalu mepet -> rawan noise,
  atau terlalu lebar -> kemungkinan data aneh / SL tidak masuk akal) ATAU
  risk:reward di bawah minimum yang ditentukan, sinyal dianggap TIDAK LAYAK
  secara risiko dan harus dibatalkan oleh caller (bukan cuma info tambahan).
  Sebelumnya tidak ada konsep ini sama sekali: semua sinyal yang lolos
  price-action langsung dikirim, terlepas dari apakah trade-nya masuk akal
  secara manajemen risiko.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from src.models import Direction


@dataclass
class RiskLevels:
    valid: bool
    stop_loss: Optional[float] = None
    take_profit_1: Optional[float] = None
    take_profit_2: Optional[float] = None
    risk_reward_1: Optional[float] = None
    risk_reward_2: Optional[float] = None
    reason: Optional[str] = None  # alasan invalid, kalau valid=False


def compute_risk_levels(
    direction: Direction,
    entry_price: float,
    structure_stop_price: float,
    atr: Optional[float],
    cfg: dict,
) -> RiskLevels:
    """
    entry_price          : harga entry (close candle trigger M5)
    structure_stop_price : level struktur acuan invalidation (= level zona,
                            yaitu swing low/high M15 yang membentuk zona)
    atr                   : ATR M5 saat ini (dipakai sbg buffer SL)
    """
    if atr is None or atr <= 0 or entry_price <= 0:
        return RiskLevels(valid=False, reason="atr_or_price_invalid")

    sl_atr_buffer_mult = cfg.get("slAtrBufferMultiplier", 0.25)
    rr_targets: List[float] = cfg.get("riskRewardTargets", [1.5, 3.0]) or []
    min_rr = cfg.get("minRiskRewardRatio", 1.2)
    min_sl_distance_pct = cfg.get("minStopDistancePct", 0.05)
    max_sl_distance_pct = cfg.get("maxStopDistancePct", 5.0)

    buffer = atr * sl_atr_buffer_mult

    if direction == Direction.BUY:
        stop_loss = structure_stop_price - buffer
        risk = entry_price - stop_loss
    else:
        stop_loss = structure_stop_price + buffer
        risk = stop_loss - entry_price

    if risk <= 0:
        return RiskLevels(valid=False, reason="non_positive_risk")

    risk_pct = (risk / entry_price) * 100
    if risk_pct < min_sl_distance_pct:
        return RiskLevels(valid=False, reason="stop_too_tight")
    if risk_pct > max_sl_distance_pct:
        return RiskLevels(valid=False, reason="stop_too_wide")

    if not rr_targets:
        return RiskLevels(valid=False, reason="no_rr_targets_configured")

    rr1 = float(rr_targets[0])
    rr2 = float(rr_targets[1]) if len(rr_targets) > 1 else None

    if rr1 < min_rr:
        return RiskLevels(valid=False, reason="risk_reward_below_minimum")

    if direction == Direction.BUY:
        tp1 = entry_price + risk * rr1
        tp2 = entry_price + risk * rr2 if rr2 is not None else None
    else:
        tp1 = entry_price - risk * rr1
        tp2 = entry_price - risk * rr2 if rr2 is not None else None

    return RiskLevels(
        valid=True,
        stop_loss=round(stop_loss, 8),
        take_profit_1=round(tp1, 8),
        take_profit_2=round(tp2, 8) if tp2 is not None else None,
        risk_reward_1=rr1,
        risk_reward_2=rr2,
    )
