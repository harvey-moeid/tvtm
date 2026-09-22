from __future__ import annotations

import os

import pytest

from src.market.exchange_adapter import get_adapter
from src.notify.notify_discord import _post
from src.storage.d1_client import D1Client


def _required_env(*names: str) -> dict[str, str] | None:
    values = {name: os.getenv(name) for name in names}
    if not all(values.values()):
        return None
    return {name: value for name, value in values.items() if value is not None}


@pytest.mark.live
def test_okx_public_api_live():
    if os.getenv("TVTM_LIVE_IO") != "1":
        pytest.skip("TVTM_LIVE_IO != 1")

    adapter = get_adapter("okx")
    candles = adapter.fetch_klines("BTC-USDT-SWAP", "5m", 10)

    assert candles
    assert len(candles) <= 10
    assert candles == sorted(candles, key=lambda candle: candle.open_time)
    assert all(candle.is_closed for candle in candles)
    assert all(candle.high >= candle.low for candle in candles)


@pytest.mark.live
def test_okx_gold_live():
    if os.getenv("TVTM_LIVE_IO") != "1":
        pytest.skip("TVTM_LIVE_IO != 1")

    adapter = get_adapter("okx")
    candles = adapter.fetch_klines("XAU-USDT-SWAP", "5m", 10)

    assert candles
    assert candles == sorted(candles, key=lambda candle: candle.open_time)
    assert all(candle.is_closed for candle in candles)


@pytest.mark.live
def test_d1_query_live():
    if os.getenv("TVTM_LIVE_IO") != "1":
        pytest.skip("TVTM_LIVE_IO != 1")

    env = _required_env(
        "CF_ACCOUNT_ID",
        "CF_D1_DATABASE_ID",
        "CF_API_TOKEN",
    )
    if env is None:
        pytest.skip("Cloudflare D1 secrets belum tersedia")

    client = D1Client(
        env["CF_ACCOUNT_ID"],
        env["CF_D1_DATABASE_ID"],
        env["CF_API_TOKEN"],
    )
    row = client.query_one("SELECT 1 AS healthcheck")
    assert row == {"healthcheck": 1}


@pytest.mark.live
def test_discord_webhook_live():
    if os.getenv("TVTM_LIVE_IO") != "1":
        pytest.skip("TVTM_LIVE_IO != 1")

    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        pytest.skip("DISCORD_WEBHOOK_URL belum tersedia")

    if os.getenv("TVTM_LIVE_DISCORD") != "1":
        pytest.skip("TVTM_LIVE_DISCORD != 1")

    assert _post(
        webhook_url,
        {
            "username": "TV Alert Relay",
            "content": "TVTM live I/O smoke test berhasil.",
        },
        "live-smoke-test",
    )
