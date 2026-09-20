from __future__ import annotations

import pytest

from src.market import exchange_adapter
from src.market.exchange_adapter import KrakenSpotAdapter, _parse_kraken_ohlc, get_adapter

M5 = 5 * 60 * 1000
M15 = 15 * 60 * 1000
# Kelipatan 15 menit supaya sejajar dengan jendela M5 maupun M15.
T0 = 1_700_000_100_000 - (1_700_000_100_000 % M15)


def _row(open_time_ms: int, o: float, h: float, l: float, c: float, v: float = 1.5) -> list:
    # Format Kraken: [time_detik, open, high, low, close, vwap, volume, count] (angka sebagai string)
    return [open_time_ms // 1000, str(o), str(h), str(l), str(c), "0", str(v), 10]


def _payload(rows: list, key: str = "XXBTZUSD") -> dict:
    return {"error": [], "result": {key: rows, "last": 123}}


def test_terdaftar_di_adapters():
    assert isinstance(get_adapter("kraken_spot"), KrakenSpotAdapter)


def test_parse_konversi_field_dan_close_time():
    rows = [_row(T0, 100, 110, 90, 105, 2.5), _row(T0 + M5, 105, 106, 104, 105.5)]
    now = T0 + 2 * M5 + 1000
    candles = _parse_kraken_ohlc(_payload(rows), "5m", 100, now)
    assert len(candles) == 3  # 2 nyata + 1 datar in-progress di jendela berjalan
    c = candles[0]
    assert (c.open_time, c.close_time) == (T0, T0 + M5 - 1)
    assert (c.open, c.high, c.low, c.close, c.volume) == (100.0, 110.0, 90.0, 105.0, 2.5)


def test_candle_berjalan_tidak_closed():
    rows = [_row(T0, 1, 2, 0.5, 1.5), _row(T0 + M5, 1.5, 2, 1, 1.8)]
    now = T0 + M5 + 60_000  # candle kedua baru berjalan 1 menit
    candles = _parse_kraken_ohlc(_payload(rows), "5m", 100, now)
    assert [c.is_closed for c in candles] == [True, False]


def test_kunci_pair_bebas_dan_urutan_ascending():
    rows = [_row(T0 + M5, 2, 3, 1, 2), _row(T0, 1, 2, 0.5, 1)]  # sengaja terbalik
    candles = _parse_kraken_ohlc(_payload(rows, key="PAXGUSD"), "5m", 100, T0 + 3 * M5)
    opens = [c.open_time for c in candles]
    assert opens == sorted(opens)


def test_gap_ditambal_candle_datar():
    rows = [_row(T0, 10, 12, 9, 11), _row(T0 + 3 * M5, 11, 13, 10, 12)]  # 2 candle hilang
    now = T0 + 4 * M5 + 1000
    candles = _parse_kraken_ohlc(_payload(rows), "5m", 100, now)
    assert [c.open_time for c in candles][:4] == [T0, T0 + M5, T0 + 2 * M5, T0 + 3 * M5]
    flat = candles[1]
    assert (flat.open, flat.high, flat.low, flat.close, flat.volume) == (11.0, 11.0, 11.0, 11.0, 0.0)
    assert flat.is_closed


def test_trailing_gap_ditambal_sampai_jendela_berjalan():
    rows = [_row(T0, 10, 12, 9, 11)]
    now = T0 + 3 * M5 + 1000  # Kraken belum punya candle utk 3 jendela terakhir
    candles = _parse_kraken_ohlc(_payload(rows), "5m", 100, now)
    assert [c.open_time for c in candles] == [T0, T0 + M5, T0 + 2 * M5, T0 + 3 * M5]
    assert [c.is_closed for c in candles] == [True, True, True, False]


def test_limit_mengambil_candle_terbaru():
    rows = [_row(T0 + i * M5, 1, 2, 0.5, 1) for i in range(10)]
    candles = _parse_kraken_ohlc(_payload(rows), "5m", 4, T0 + 10 * M5 + 1000)
    assert len(candles) == 4
    assert candles[-1].open_time >= T0 + 9 * M5


def test_error_field_kraken_melempar_exception():
    with pytest.raises(RuntimeError, match="Unknown asset pair"):
        _parse_kraken_ohlc({"error": ["EQuery:Unknown asset pair"], "result": {}}, "5m", 10, T0)


def test_result_kosong_melempar_exception():
    with pytest.raises(RuntimeError):
        _parse_kraken_ohlc({"error": [], "result": {"last": 1}}, "5m", 10, T0)


def test_fetch_klines_memanggil_endpoint_dan_interval(monkeypatch):
    captured = {}

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return _payload([_row(T0, 1, 2, 0.5, 1)])

    def fake_get(url, params=None, timeout=None):
        captured.update(url=url, params=params)
        return FakeResp()

    monkeypatch.setattr(exchange_adapter.requests, "get", fake_get)
    KrakenSpotAdapter().fetch_klines("XBTUSD", "15m", 50)
    assert captured["url"].endswith("/0/public/OHLC")
    assert captured["params"] == {"pair": "XBTUSD", "interval": 15}


def test_timeframe_tidak_didukung():
    with pytest.raises(ValueError):
        KrakenSpotAdapter().fetch_klines("XBTUSD", "1h", 10)
