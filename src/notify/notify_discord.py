"""
Notifikasi Discord via webhook — PRD §15/§16 (format payload signal).
"""

from __future__ import annotations

import logging

import requests

from src.models import Signal

log = logging.getLogger("notify_discord")

_EMOJI = {"BUY": "🟢", "SELL": "🔴"}


def _build_embed(signal: Signal) -> dict:
    emoji = _EMOJI.get(signal.direction.value, "⚪")
    return {
        "username": "TV Alert Relay",
        "embeds": [
            {
                "title": f"{emoji} {signal.direction.value} — {signal.symbol} ({signal.timeframe})",
                "color": 3066993 if signal.direction.value == "BUY" else 15158332,
                "fields": [
                    {"name": "Market", "value": signal.market, "inline": True},
                    {"name": "Bias M15", "value": signal.m15_bias.value, "inline": True},
                    {"name": "Price", "value": f"{signal.price}", "inline": True},
                    {
                        "name": "Zone",
                        "value": f"{signal.zone_type} @ {signal.zone_level}",
                        "inline": True,
                    },
                    {"name": "Structure Event", "value": signal.structure_event, "inline": True},
                    {"name": "Pattern", "value": signal.pattern, "inline": True},
                    {"name": "Candle Time", "value": signal.candle_time_iso, "inline": False},
                ],
                "footer": {"text": signal.signal_key},
            }
        ],
    }


def send_discord_signal(webhook_url: str, signal: Signal) -> bool:
    payload = _build_embed(signal)
    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        resp.raise_for_status()
        return True
    except Exception as e:  # noqa: BLE001
        log.error("Gagal kirim Discord untuk %s: %s", signal.signal_key, e)
        return False
