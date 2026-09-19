"""
Cooldown & duplicate prevention - PRD 14, + upgrade rate-limit waktu aktif.

Dua lapis proteksi independen:

1. is_in_cooldown(cooldown_key)
   Suppression PERMANEN per cooldown_key (symbol+timeframe+zone+structure_event
   +direction). cooldown_key otomatis berganti begitu ada BOS/CHoCH baru / zona
   baru (menyertakan structure_event_candle_time), jadi layer ini murni
   "jangan ulang notif untuk setup struktural yang SAMA PERSIS". Perilaku
   IDENTIK dengan versi awal.

2. is_rate_limited(symbol, timeframe, direction, cooldown_minutes)  [BARU]
   Versi awal punya parameter `cooldown_minutes` di strategy.json tapi TIDAK
   PERNAH dipakai di kode (docstring versi awal mengakuinya secara eksplisit)
   - jadi kalaupun di-tuning, tidak ada efeknya sama sekali. Fungsi ini
   mengisi kekosongan itu: proteksi tambahan berbasis waktu murni, supaya
   walau setup struktural berbeda (zona baru / event baru, sehingga
   cooldown_key ikut berbeda), tetap ada jeda minimum antar notifikasi untuk
   symbol+timeframe+arah yang sama - mencegah spam saat market membentuk
   banyak BOS/CHoCH kecil berturut-turut dalam waktu singkat (choppy
   breakout-retest-breakout).
   cooldown_minutes <= 0 -> layer ini dimatikan (no-op, return False),
   sehingga default lama (kalau operator set 0) tetap bisa direplikasi.
"""

from __future__ import annotations

from src.storage.d1_client import D1Client


def build_cooldown_key(symbol: str, timeframe: str, zone_type: str, zone_level: float,
                        structure_event: str, structure_event_candle_time, direction: str) -> str:
    return (
        f"{symbol}:{timeframe}:{zone_type}:{round(zone_level, 6)}:"
        f"{structure_event}:{structure_event_candle_time}:{direction}"
    )


def is_in_cooldown(d1: D1Client, cooldown_key: str) -> bool:
    row = d1.query_one(
        "SELECT id FROM signals WHERE cooldown_key = ? AND notified = 1 LIMIT 1",
        [cooldown_key],
    )
    return row is not None


def is_rate_limited(
    d1: D1Client, symbol: str, timeframe: str, direction: str, cooldown_minutes: int
) -> bool:
    if cooldown_minutes is None or cooldown_minutes <= 0:
        return False
    row = d1.query_one(
        """
        SELECT id FROM signals
        WHERE symbol = ? AND timeframe = ? AND direction = ? AND notified = 1
          AND created_at >= strftime('%Y-%m-%dT%H:%M:%fZ', 'now', ?)
        LIMIT 1
        """,
        [symbol, timeframe, direction, f"-{int(cooldown_minutes)} minutes"],
    )
    return row is not None
