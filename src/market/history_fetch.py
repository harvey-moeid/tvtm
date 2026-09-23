"""
Ambil histori candle OKX JAUH lebih panjang dari batas 300/request endpoint
biasa, lewat endpoint `history-candles` (maks 100 candle/request) dengan
pagination mundur pakai parameter `after` (timestamp ms - "candle SEBELUM
timestamp ini").

HANYA dipakai untuk backtest (scripts/backtest.py) - runtime cron
(src/market/fetch_candles.py, dipakai check-signal.yml) TIDAK diubah dan
TETAP memakai endpoint /market/candles biasa seperti sebelumnya.
"""

from __future__ import annotations

import time
from typing import List, Optional

import requests

from src.models import Candle

OKX_BASE = "https://www.okx.com"
_BAR = {"5m": "5m", "15m": "15m"}
_INTERVAL_MS = {"5m": 5 * 60 * 1000, "15m": 15 * 60 * 1000}
_HISTORY_MAX_LIMIT = 100
_RATE_LIMIT_SLEEP_SEC = 0.15  # OKX public endpoint: 20 req/2s - kasih jeda aman


def fetch_history_candles(inst_id: str, timeframe: str, target_count: int) -> List[Candle]:
    """Ambil s.d. `target_count` candle CLOSED terbaru (ascending open_time),
    paginasi mundur (candle demi candle lebih lama) pakai parameter `after`."""
    if timeframe not in _BAR:
        raise ValueError(f"Timeframe tidak didukung: {timeframe}")

    interval_ms = _INTERVAL_MS[timeframe]
    # Sama seperti src/market/exchange_adapter.py: instrumen -SWAP melaporkan
    # `vol` dalam jumlah KONTRAK, bukan koin dasar - pakai volCcy (index 6).
    vol_idx = 6 if inst_id.endswith("-SWAP") else 5
    collected: List[Candle] = []
    after_ts: Optional[int] = None

    while len(collected) < target_count:
        params = {"instId": inst_id, "bar": _BAR[timeframe], "limit": _HISTORY_MAX_LIMIT}
        if after_ts is not None:
            params["after"] = str(after_ts)

        resp = requests.get(
            f"{OKX_BASE}/api/v5/market/history-candles", params=params, timeout=20
        )
        resp.raise_for_status()
        body = resp.json()
        if str(body.get("code", "")) != "0":
            raise RuntimeError(f"OKX history-candles error {body.get('code')}: {body.get('msg')}")

        rows = body.get("data") or []
        if not rows:
            break  # habis, tidak ada data lebih lama lagi

        for r in rows:
            open_time = int(r[0])
            collected.append(
                Candle(
                    open_time=open_time,
                    close_time=open_time + interval_ms - 1,
                    open=float(r[1]), high=float(r[2]), low=float(r[3]), close=float(r[4]),
                    volume=float(r[vol_idx]) if len(r) > vol_idx else float(r[5]),
                    is_closed=True,  # history-candles hanya pernah mengembalikan candle closed
                )
            )

        after_ts = int(rows[-1][0])  # baris terlama di batch ini -> titik pagination berikutnya
        time.sleep(_RATE_LIMIT_SLEEP_SEC)

    collected.sort(key=lambda c: c.open_time)
    # Buang duplikat kalau ada overlap antar halaman.
    deduped: List[Candle] = []
    seen = set()
    for c in collected:
        if c.open_time in seen:
            continue
        seen.add(c.open_time)
        deduped.append(c)

    return deduped[-target_count:] if len(deduped) > target_count else deduped
