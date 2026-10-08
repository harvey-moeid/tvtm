from __future__ import annotations

import os

import pytest

from src.market.exchange_adapter import get_adapter
from src.notify.notify_discord import _post
import base64
import json
import requests


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
    assert any(candle.is_closed for candle in candles)
    assert all(candle.high >= candle.low for candle in candles)


@pytest.mark.live
def test_okx_gold_live():
    if os.getenv("TVTM_LIVE_IO") != "1":
        pytest.skip("TVTM_LIVE_IO != 1")

    adapter = get_adapter("okx")
    candles = adapter.fetch_klines("XAU-USDT-SWAP", "5m", 10)

    assert candles
    assert candles == sorted(candles, key=lambda candle: candle.open_time)
    assert any(candle.is_closed for candle in candles)


@pytest.mark.live
def test_github_state_live():
    if os.getenv("TVTM_LIVE_IO") != "1":
        pytest.skip("TVTM_LIVE_IO != 1")
    required = _required_env("GITHUB_TOKEN", "GITHUB_REPOSITORY")
    if required is None:
        pytest.skip("GitHub repository/token tidak tersedia")
    repo = required["GITHUB_REPOSITORY"]
    res = requests.get(
        f"https://api.github.com/repos/{repo}/contents/state.json",
        params={"ref": os.getenv("TVTM_STATE_BRANCH", "tvtm-state")},
        headers={"Authorization": f"Bearer {required['GITHUB_TOKEN']}",
                 "Accept": "application/vnd.github+json"},
        timeout=20,
    )
    res.raise_for_status()
    state = json.loads(base64.b64decode(res.json()["content"]))
    assert state["version"] == 1
    assert isinstance(state["trades"], list)
    assert isinstance(state["signals"], list)


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
