from __future__ import annotations

import pytest

from src.strategy import strategy
from src.strategy.strategy import MarketDataUnavailable, evaluate_market

MARKET = {
    "id": "TEST",
    "symbol": "BTCUSDT",
    "market": "spot",
    "exchange": "kraken_spot",
    "exchange_symbol": "XBTUSD",
}
CFG = {"minHistoricalCandles": 200, "swingLookback": 2}


def test_m15_kosong_melempar_market_data_unavailable(monkeypatch):
    monkeypatch.setattr(strategy, "fetch_closed_candles", lambda *a, **k: None)
    with pytest.raises(MarketDataUnavailable):
        evaluate_market(MARKET, CFG, d1=None)


def test_m5_kosong_melempar_market_data_unavailable(monkeypatch):
    calls = []

    def fake_fetch(exchange, symbol, timeframe, min_history):
        calls.append(timeframe)
        return [object()] if timeframe == "15m" else None

    monkeypatch.setattr(strategy, "fetch_closed_candles", fake_fetch)
    with pytest.raises(MarketDataUnavailable):
        evaluate_market(MARKET, CFG, d1=None)
    assert calls == ["15m", "5m"]
