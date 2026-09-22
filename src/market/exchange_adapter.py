"""
Adapter exchange/provider market data.
Memisahkan simbol internal (BTCUSDT, GOLDUSDT) dari simbol exchange aktual
(mis. BTC-USDT-SWAP atau XAU-USDT-SWAP di OKX) sesuai PRD bagian 1 dan 7.

Setiap adapter wajib:
- return list[Candle] terurut ascending berdasarkan open_time
- HANYA mengembalikan candle yang sudah closed/final (PRD bagian 5)
- retry ringan di level fetch_candles.py, bukan di sini
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import List

import requests

from src.models import Candle

BINANCE_FUTURES_BASE = "https://fapi.binance.com"
BINANCE_SPOT_BASE = "https://api.binance.com"

_INTERVAL_MS = {
    "5m": 5 * 60 * 1000,
    "15m": 15 * 60 * 1000,
}


class ExchangeAdapter(ABC):
    name: str

    @abstractmethod
    def fetch_klines(self, exchange_symbol: str, timeframe: str, limit: int) -> List[Candle]:
        raise NotImplementedError


class BinanceFuturesAdapter(ExchangeAdapter):
    """USDT-M Futures public klines (dipakai untuk BTCUSDT)."""

    name = "binance_futures"

    def fetch_klines(self, exchange_symbol: str, timeframe: str, limit: int) -> List[Candle]:
        url = f"{BINANCE_FUTURES_BASE}/fapi/v1/klines"
        return _fetch_binance_style(url, exchange_symbol, timeframe, limit)


class BinanceSpotAdapter(ExchangeAdapter):
    """Spot public klines untuk instrumen spot yang dikonfigurasi."""

    name = "binance_spot"

    def fetch_klines(self, exchange_symbol: str, timeframe: str, limit: int) -> List[Candle]:
        url = f"{BINANCE_SPOT_BASE}/api/v3/klines"
        return _fetch_binance_style(url, exchange_symbol, timeframe, limit)


def _fetch_binance_style(url: str, symbol: str, timeframe: str, limit: int) -> List[Candle]:
    params = {"symbol": symbol, "interval": timeframe, "limit": limit}
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    raw = resp.json()

    now_ms = int(time.time() * 1000)
    interval_ms = _INTERVAL_MS.get(timeframe, 0)

    candles: List[Candle] = []
    for row in raw:
        open_time, o, h, l, c, v, close_time = (
            row[0], row[1], row[2], row[3], row[4], row[5], row[6]
        )
        # Candle dianggap closed hanya jika close_time sudah lewat DAN
        # sudah melewati open_time + interval penuh (double-check terhadap jam server).
        is_closed = close_time < now_ms and (open_time + interval_ms) <= now_ms
        candles.append(
            Candle(
                open_time=int(open_time),
                close_time=int(close_time),
                open=float(o),
                high=float(h),
                low=float(l),
                close=float(c),
                volume=float(v),
                is_closed=is_closed,
            )
        )
    return candles


KRAKEN_BASE = "https://api.kraken.com"

_KRAKEN_INTERVAL_MIN = {"5m": 5, "15m": 15}

# Batas pengaman jumlah candle datar yang boleh disisipkan saat menambal gap.
_MAX_GAP_FILL = 720


class KrakenSpotAdapter(ExchangeAdapter):
    """
    Kraken spot public OHLC. Alternatif sumber data (bukan yang aktif di symbols.json)
    kalau OKX bermasalah; Binance membalas HTTP 451 ke IP runner GitHub Actions (AS).

    exchange_symbol = kode pair Kraken, mis. "XBTUSD" (BTC/USD). Harga dalam USD, bukan USDT.
    """

    name = "kraken_spot"

    def fetch_klines(self, exchange_symbol: str, timeframe: str, limit: int) -> List[Candle]:
        if timeframe not in _KRAKEN_INTERVAL_MIN:
            raise ValueError(f"Timeframe tidak didukung Kraken adapter: {timeframe}")
        resp = requests.get(
            f"{KRAKEN_BASE}/0/public/OHLC",
            params={"pair": exchange_symbol, "interval": _KRAKEN_INTERVAL_MIN[timeframe]},
            timeout=15,
        )
        resp.raise_for_status()
        return _parse_kraken_ohlc(resp.json(), timeframe, limit, int(time.time() * 1000))


def _parse_kraken_ohlc(payload: dict, timeframe: str, limit: int, now_ms: int) -> List[Candle]:
    """
    Ubah respons Kraken OHLC jadi list[Candle] ascending.

    - Kraken membalas HTTP 200 walau gagal; kegagalan ada di field "error".
    - Kunci pair di "result" bisa berbeda dari yang diminta (XBTUSD -> XXBTZUSD),
      jadi ambil kunci selain "last".
    - Kraken hanya membuat candle kalau ada transaksi. Gap ditambal dengan candle
      datar (OHLC = close sebelumnya, volume 0) supaya deret waktu kontigu, sama
      seperti feed Binance. Catatan: candle datar menurunkan rata-rata volume kalau
      filter volume diaktifkan.
    - Candle terakhir dari Kraken adalah candle yang sedang berjalan; ditandai
      is_closed=False sehingga dibuang oleh fetch_closed_candles.
    """
    errors = payload.get("error") or []
    if errors:
        raise RuntimeError("Kraken API error: " + ", ".join(str(e) for e in errors))

    result = payload.get("result") or {}
    rows = next((v for k, v in result.items() if k != "last"), None)
    if not rows:
        raise RuntimeError("Kraken OHLC kosong")

    interval_ms = _INTERVAL_MS[timeframe]

    def build(open_time: int, o: float, h: float, l: float, c: float, v: float) -> Candle:
        return Candle(
            open_time=open_time,
            close_time=open_time + interval_ms - 1,
            open=o,
            high=h,
            low=l,
            close=c,
            volume=v,
            is_closed=(open_time + interval_ms) <= now_ms,
        )

    real = sorted(
        (
            build(int(r[0]) * 1000, float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[6]))
            for r in rows
        ),
        key=lambda c: c.open_time,
    )

    candles: List[Candle] = []
    filled = 0
    current_window = (now_ms // interval_ms) * interval_ms
    for i, candle in enumerate(real):
        candles.append(candle)
        next_open = real[i + 1].open_time if i + 1 < len(real) else current_window + interval_ms
        t = candle.open_time + interval_ms
        while t < next_open and filled < _MAX_GAP_FILL:
            candles.append(build(t, candle.close, candle.close, candle.close, candle.close, 0.0))
            t += interval_ms
            filled += 1

    return candles[-limit:]


OKX_BASE = "https://www.okx.com"

_OKX_BAR = {"5m": "5m", "15m": "15m"}

# Batas maksimum parameter limit endpoint /api/v5/market/candles.
_OKX_MAX_LIMIT = 300


class OkxAdapter(ExchangeAdapter):
    """
    OKX v5 public market data (tanpa API key), spot maupun perpetual swap.

    exchange_symbol = instId OKX, mis. "BTC-USDT-SWAP" (perp USDT-margined, setara
    Binance USDT-M futures) atau instrumen spot lain. Dipakai karena Binance (HTTP 451)
    dan Bybit (HTTP 403) memblokir IP runner GitHub Actions.
    """

    name = "okx"

    def fetch_klines(self, exchange_symbol: str, timeframe: str, limit: int) -> List[Candle]:
        if timeframe not in _OKX_BAR:
            raise ValueError(f"Timeframe tidak didukung OKX adapter: {timeframe}")
        resp = requests.get(
            f"{OKX_BASE}/api/v5/market/candles",
            params={
                "instId": exchange_symbol,
                "bar": _OKX_BAR[timeframe],
                "limit": min(limit, _OKX_MAX_LIMIT),
            },
            timeout=15,
        )
        resp.raise_for_status()
        return _parse_okx_candles(resp.json(), exchange_symbol, timeframe, int(time.time() * 1000))


def _parse_okx_candles(payload: dict, inst_id: str, timeframe: str, now_ms: int) -> List[Candle]:
    """
    Ubah respons OKX /market/candles jadi list[Candle] ascending.

    - OKX membalas HTTP 200 walau gagal; kegagalan ada di field "code" (bukan "0"),
      mis. 51001 = instId tidak ada.
    - Baris: [ts_ms, open, high, low, close, vol, volCcy, volCcyQuote, confirm],
      terurut TERBARU dulu. confirm "1" = candle sudah closed, "0" = masih berjalan.
    - Satuan volume beda antar jenis instrumen: SPOT -> `vol` sudah dalam koin dasar
      SWAP -> `vol` dalam jumlah kontrak, sedangkan `volCcy` dalam koin dasar.
      Dipakai volume koin dasar supaya konsisten dengan feed Binance.
    - Interval tanpa transaksi tetap dikirim OKX sebagai candle datar (volume 0),
      jadi deret waktunya kontigu dan tidak perlu ditambal di sini.
    """
    code = str(payload.get("code", ""))
    if code != "0":
        raise RuntimeError(f"OKX API error {code}: {payload.get('msg', '')}")

    rows = payload.get("data") or []
    if not rows:
        raise RuntimeError("OKX candles kosong")

    interval_ms = _INTERVAL_MS[timeframe]
    vol_idx = 6 if inst_id.endswith("-SWAP") else 5

    candles: List[Candle] = []
    for r in rows:
        open_time = int(r[0])
        ended = (open_time + interval_ms) <= now_ms
        confirmed = (str(r[8]) == "1") if len(r) > 8 else ended
        volume = float(r[vol_idx]) if len(r) > vol_idx else float(r[5])
        candles.append(
            Candle(
                open_time=open_time,
                close_time=open_time + interval_ms - 1,
                open=float(r[1]),
                high=float(r[2]),
                low=float(r[3]),
                close=float(r[4]),
                volume=volume,
                is_closed=confirmed and ended,
            )
        )
    candles.sort(key=lambda c: c.open_time)
    return candles


ADAPTERS = {
    "binance_futures": BinanceFuturesAdapter(),
    "binance_spot": BinanceSpotAdapter(),
    "kraken_spot": KrakenSpotAdapter(),
    "okx": OkxAdapter(),
}


def get_adapter(name: str) -> ExchangeAdapter:
    if name not in ADAPTERS:
        raise ValueError(f"Exchange adapter tidak dikenal: {name}")
    return ADAPTERS[name]