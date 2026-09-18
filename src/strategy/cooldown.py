"""
Cooldown & duplicate prevention — PRD §14.

Suppression PERMANEN per cooldown_key (symbol+timeframe+zone+structure_event+direction)
selama record dengan key yang sama SUDAH pernah ter-notify di D1. cooldown_key
otomatis "invalid" begitu ada BOS/CHoCH baru / zona baru, karena key tsb
menyertakan structure_event_candle_time (timestamp event pembentuk zona) —
begitu event berganti, key ikut berganti, sehingga syarat PRD §14
(BOS/CHoCH baru, zona baru, atau setup lama invalid) terpenuhi otomatis.

Tambahan: cooldown_minutes sebagai rate-limit suplemen supaya symbol/timeframe
yang sama tidak spam notifikasi walau struktur belum berubah sama sekali
dalam rentang waktu sangat pendek (proteksi ekstra, bukan pengganti aturan di atas).
"""

from __future__ import annotations

from src.storage.d1_client import D1Client


def build_cooldown_key(symbol: str, timeframe: str, zone_type: str, zone_level: float,
                        structure_event: str, structure_event_candle_time, direction: str) -> str:
    return (
        f"{symbol}:{timeframe}:{zone_type}:{round(zone_level, 6)}:"
        f"{structure_event}:{structure_event_candle_time}:{direction}"
    )


def is_in_cooldown(d1: D1Client, cooldown_key: str, cooldown_minutes: int) -> bool:
    """
    True kalau cooldown_key ini SUDAH pernah dinotifikasi sebelumnya.
    Karena cooldown_key menyertakan structure_event_candle_time, key otomatis
    berubah begitu ada BOS/CHoCH baru atau zona baru terbentuk (PRD §14),
    jadi suppression di sini valid bersifat permanen per key — bukan time-based.

    `cooldown_minutes` tetap disediakan di strategy.json sebagai parameter
    tuning eksplisit (mis. kalau ke depan mau ditambah rate-limit tambahan
    per symbol+timeframe di luar aturan cooldown_key), tapi versi ini belum
    memakainya secara aktif supaya perilaku tetap sesuai PRD §14 apa adanya.
    """
    row = d1.query_one(
        "SELECT id FROM signals WHERE cooldown_key = ? AND notified = 1 LIMIT 1",
        [cooldown_key],
    )
    return row is not None
