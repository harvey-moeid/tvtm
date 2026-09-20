from __future__ import annotations

import pytest

from src.market import exchange_adapter
from src.market.exchange_adapter import OkxAdapter, _parse_okx_candles, get_adapter

M5 = 5 * 60 * 1000

# Sampel respons nyata OKX /market/candles (PAXG-USDT 5m): urutan TERBARU dulu,
# candle pertama masih berjalan (confirm "0"), beberapa candle datar tanpa transaksi.
PAXG_SAMPLE = {
    "code": "0",
    "msg": "",
    "data": [
        ["1789869000000", "4366.2", "4366.2", "4366.2", "4366.2", "0", "0", "0", "0"],
        ["1789868700000", "4366.2", "4366.2", "4366.2", "4366.2", "0.002267", "9.8981754", "9.8981754", "1"],
        ["1789868400000", "4366.1", "4366.1", "4366.1", "4366.1", "0", "0", "0", "1"],
        ["1789868100000", "4366.1", "4366.1", "4366.1", "4366.1", "1.185289", "5175.0903029", "5175.0903029", "1"],
        ["1789867800000", "4366.3", "4366.3", "4366.3", "4366.3", "0.8", "3493.04", "3493.04", "1"],
    ],
}
NOW = 1789869000000 + 60_000  # 1 menit setelah candle berjalan dibuka


def test_terdaftar_di_adapters():
    assert isinstance(get_adapter("okx"), OkxAdapter)


def test_urutan_ascending_dan_candle_berjalan_tidak_closed():
    candles = _parse_okx_candles(PAXG_SAMPLE, "PAXG-USDT", "5m", NOW)
    opens = [c.open_time for c in candles]
    assert opens == sorted(opens)
    assert [c.is_closed for c in candles] == [True, True, True, True, False]


def test_konversi_field_dan_close_time():
    candles = _parse_okx_candles(PAXG_SAMPLE, "PAXG-USDT", "5m", NOW)
    c = candles[0]  # candle tertua: 1789867800000
    assert (c.open_time, c.close_time) == (1789867800000, 1789867800000 + M5 - 1)
    assert (c.open, c.high, c.low, c.close) == (4366.3, 4366.3, 4366.3, 4366.3)


def test_volume_spot_pakai_vol_koin_dasar():
    candles = _parse_okx_candles(PAXG_SAMPLE, "PAXG-USDT", "5m", NOW)
    assert candles[0].volume == 0.8  # bukan volCcy (3493.04 = nilai USDT)


def test_volume_swap_pakai_volccy_koin_dasar():
    payload = {"code": "0", "data": [["1789867800000", "1", "2", "0.5", "1.5", "250", "2.5", "12345", "1"]]}
    candles = _parse_okx_candles(payload, "BTC-USDT-SWAP", "5m", NOW)
    assert candles[0].volume == 2.5  # volCcy (BTC), bukan 250 kontrak


def test_confirm_1_tapi_jendela_belum_selesai_tetap_tidak_closed():
    # Jam runner tertinggal: candle ditandai confirm=1 tapi waktu belum melewati open+interval.
    payload = {"code": "0", "data": [["1789867800000", "1", "2", "0.5", "1.5", "1", "1", "1", "1"]]}
    candles = _parse_okx_candles(payload, "PAXG-USDT", "5m", 1789867800000 + M5 - 1)
    assert candles[0].is_closed is False


def test_kode_error_melempar_exception():
    payload = {"code": "51001", "msg": "Instrument ID doesn't exist.", "data": []}
    with pytest.raises(RuntimeError, match="51001"):
        _parse_okx_candles(payload, "XXX-USDT", "5m", NOW)


def test_data_kosong_melempar_exception():
    with pytest.raises(RuntimeError):
        _parse_okx_candles({"code": "0", "data": []}, "PAXG-USDT", "5m", NOW)


def test_fetch_klines_memanggil_endpoint_dan_membatasi_limit(monkeypatch):
    captured = {}

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return PAXG_SAMPLE

    def fake_get(url, params=None, timeout=None):
        captured.update(url=url, params=params)
        return FakeResp()

    monkeypatch.setattr(exchange_adapter.requests, "get", fake_get)
    OkxAdapter().fetch_klines("BTC-USDT-SWAP", "15m", 1000)
    assert captured["url"].endswith("/api/v5/market/candles")
    assert captured["params"] == {"instId": "BTC-USDT-SWAP", "bar": "15m", "limit": 300}


def test_timeframe_tidak_didukung():
    with pytest.raises(ValueError):
        OkxAdapter().fetch_klines("BTC-USDT-SWAP", "1h", 10)
