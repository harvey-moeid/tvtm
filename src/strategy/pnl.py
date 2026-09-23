"""
Pure PnL / R-multiple math - dipakai bersama oleh:
  - src/strategy/tracker.py   (live position tracking, hasil ditulis ke D1)
  - src/backtest/simulator.py (walk-forward backtest, in-memory)

Dipisah jadi modul sendiri (sebelumnya duplikat sebagai fungsi private di
tracker.py) supaya kedua jalur SELALU menghitung R-multiple & PnL% dengan
rumus yang identik - backtest yang memakai rumus berbeda dari live tracking
akan menghasilkan metrik yang menyesatkan (tidak benar-benar merepresentasikan
apa yang akan terjadi kalau strategi ini jalan live).
"""

from __future__ import annotations

from src.models import Direction


def r_multiple(entry: float, stop: float, exit_price: float, direction: Direction) -> float:
    """R-multiple = seberapa banyak kelipatan risiko awal (jarak entry->stop)
    yang didapat/hilang di exit_price. Positif = untung, negatif = rugi."""
    risk = abs(entry - stop)
    if risk <= 0:
        return 0.0
    return (exit_price - entry) / risk if direction == Direction.BUY else (entry - exit_price) / risk


def pnl_pct(entry: float, exit_price: float, direction: Direction) -> float:
    """PnL dalam persen dari harga entry (tanpa leverage/fee - murni pergerakan harga)."""
    signed = (exit_price - entry) if direction == Direction.BUY else (entry - exit_price)
    return signed / entry * 100 if entry else 0.0
