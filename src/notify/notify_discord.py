"""
Notifikasi Discord via webhook - PRD 15/16 (format payload signal).

UPGRADE: embed sekarang menampilkan Stop Loss dan Take Profit (+ R:R) kalau
signal membawa data risk management (lihat src/strategy/risk.py). Field ini
ditambahkan secara kondisional supaya tetap backward compatible untuk signal
lama/hasil test yang tidak mengisi field risk sama sekali.
"""

from __future__ import annotations

import logging

import requests

from src.models import Signal

log = logging.getLogger("notify_discord")

_EMOJI = {"BUY": "\U0001F7E2", "SELL": "\U0001F534"}  # green circle / red circle
_DEFAULT_EMOJI = "\u26AA"  # white circle


def _build_embed(signal: Signal) -> dict:
    emoji = _EMOJI.get(signal.direction.value, _DEFAULT_EMOJI)

    fields = [
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
    ]

    if signal.stop_loss is not None:
        fields.append({"name": "Stop Loss", "value": f"{signal.stop_loss}", "inline": True})

    if signal.take_profit_1 is not None:
        tp_parts = [f"TP1 {signal.take_profit_1} ({signal.risk_reward_1}R)"]
        if signal.take_profit_2 is not None:
            tp_parts.append(f"TP2 {signal.take_profit_2} ({signal.risk_reward_2}R)")
        fields.append({"name": "Take Profit", "value": " | ".join(tp_parts), "inline": True})

    fields.append({"name": "Candle Time", "value": signal.candle_time_iso, "inline": False})

    return {
        "username": "TV Alert Relay",
        "embeds": [
            {
                "title": f"{emoji} {signal.direction.value} - {signal.symbol} ({signal.timeframe})",
                "color": 3066993 if signal.direction.value == "BUY" else 15158332,
                "fields": fields,
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
