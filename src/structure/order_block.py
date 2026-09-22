"""Order Block (OB) detector.

Definisi yang dipakai di sini (varian price-action paling umum, bukan
volume-profile-based OB): candle BERLAWANAN arah TERAKHIR sebelum sebuah
displacement (gerakan impulsif beruntun searah) yang berujung pada BOS/CHoCH.

Bullish OB : candle bearish terakhir sebelum rangkaian candle bullish yang
             menembus swing high (BOS_BULLISH/CHOCH_BULLISH).
Bearish OB : candle bullish terakhir sebelum rangkaian candle bearish yang
             menembus swing low (BOS_BEARISH/CHOCH_BEARISH).

Zona OB = [low, high] candle tersebut - area di mana order institusional
diasumsikan terkumpul sebelum displacement; retest ke zona ini (sebelum
harga melanjutkan arah displacement) jadi titik entry konfirmasi.

`lookback` membatasi berapa candle ke belakang dari titik event yang dicari
untuk candle berlawanan-arah terakhir - default 10, cukup untuk kebanyakan
displacement wajar tanpa menyeret OB yang sudah terlalu basi/jauh.
"""

from __future__ import annotations

from typing import List, Optional

from src.models import Candle, OrderBlock, StructureEvent

_BULLISH_EVENTS = (StructureEvent.BOS_BULLISH, StructureEvent.CHOCH_BULLISH)
_BEARISH_EVENTS = (StructureEvent.BOS_BEARISH, StructureEvent.CHOCH_BEARISH)


def detect_order_block(
    candles: List[Candle],
    structure_event: StructureEvent,
    event_candle_time: Optional[int],
    lookback: int = 10,
) -> Optional[OrderBlock]:
    if structure_event not in _BULLISH_EVENTS and structure_event not in _BEARISH_EVENTS:
        return None
    if event_candle_time is None:
        return None

    event_index = next(
        (i for i, c in enumerate(candles) if c.open_time == event_candle_time),
        None,
    )
    if event_index is None:
        return None

    window_start = max(0, event_index - lookback)
    window = candles[window_start:event_index]
    if not window:
        return None

    is_bullish_event = structure_event in _BULLISH_EVENTS

    # Cari dari candle paling dekat ke event mundur ke belakang: candle
    # berlawanan arah displacement pertama yang ditemukan adalah OB-nya.
    for candle in reversed(window):
        if is_bullish_event and candle.is_bearish:
            return OrderBlock(
                direction="bullish",
                top=candle.high,
                bottom=candle.low,
                formed_at_candle_time=candle.open_time,
                structure_event=structure_event,
            )
        if not is_bullish_event and candle.is_bullish:
            return OrderBlock(
                direction="bearish",
                top=candle.high,
                bottom=candle.low,
                formed_at_candle_time=candle.open_time,
                structure_event=structure_event,
            )

    return None


def mark_mitigated(
    ob: Optional[OrderBlock],
    candles_after: List[Candle],
    event_candle_time: Optional[int] = None,
) -> Optional[OrderBlock]:
    """Tandai OB sebagai mitigated setelah displacement/event candle.

    Candle event yang menciptakan displacement tidak dihitung sebagai retest.
    Ini mencegah OB langsung dianggap mitigated hanya karena wick displacement
    menyentuh kembali area candle pembentuk OB.
    """

    if ob is None:
        return None

    if event_candle_time is not None:
        candidates = [
            c for c in candles_after if c.open_time > event_candle_time
        ]
    else:
        # Backward-compatible fallback untuk caller lama: tanpa event time,
        # semua candle setelah OB dianggap kandidat mitigasi.
        candidates = [
            c
            for c in candles_after
            if c.open_time > ob.formed_at_candle_time
        ]

    touched = any(ob.is_touched_by(c) for c in candidates)
    if not touched:
        return ob

    return OrderBlock(
        direction=ob.direction,
        top=ob.top,
        bottom=ob.bottom,
        formed_at_candle_time=ob.formed_at_candle_time,
        structure_event=ob.structure_event,
        mitigated=True,
    )
