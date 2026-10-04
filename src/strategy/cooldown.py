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

def build_cooldown_key(symbol: str, timeframe: str, zone_type: str, zone_level: float,
                        structure_event: str, structure_event_candle_time, direction: str) -> str:
    return (
        f"{symbol}:{timeframe}:{zone_type}:{round(zone_level, 6)}:"
        f"{structure_event}:{structure_event_candle_time}:{direction}"
    )


def is_in_cooldown(store, cooldown_key: str) -> bool:
    return store.has_notified_cooldown(cooldown_key)


def is_rate_limited(
    store, symbol: str, timeframe: str, direction: str, cooldown_minutes: int
) -> bool:
    if cooldown_minutes is None or cooldown_minutes <= 0:
        return False
    return store.was_notified_recently(symbol, timeframe, direction, int(cooldown_minutes))
