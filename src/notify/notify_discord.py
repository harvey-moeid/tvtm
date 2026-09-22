"""Discord webhook notification client."""

from __future__ import annotations

import logging

import requests

log = logging.getLogger("notify_discord")


def _post(url: str, payload: dict, label: str) -> bool:
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return True
    except Exception as exc:
        log.error("Discord %s gagal: %s", label, exc)
        return False


def send_discord_signal(webhook_url, signal):
    fields = [
        {"name": "Market", "value": signal.market, "inline": True},
        {"name": "Bias M15", "value": signal.m15_bias.value, "inline": True},
        {"name": "Price", "value": str(signal.price), "inline": True},
        {
            "name": "Zone",
            "value": f"{signal.zone_type} @ {signal.zone_level}",
            "inline": True,
        },
        {
            "name": "Structure",
            "value": signal.structure_event,
            "inline": True,
        },
        {"name": "Pattern", "value": signal.pattern, "inline": True},
    ]

    if signal.stop_loss is not None:
        fields.append(
            {"name": "Stop Loss", "value": str(signal.stop_loss), "inline": True}
        )

    if signal.take_profit_1 is not None:
        tp2 = (
            f" | TP2 {signal.take_profit_2} ({signal.risk_reward_2}R)"
            if signal.take_profit_2 is not None
            else ""
        )
        fields.append(
            {
                "name": "Take Profit",
                "value": (
                    f"TP1 {signal.take_profit_1} "
                    f"({signal.risk_reward_1}R){tp2}"
                ),
                "inline": True,
            }
        )

    fields.append(
        {
            "name": "Confidence",
            "value": f"{signal.confidence_pct}% | Score {signal.score}/10",
            "inline": True,
        }
    )

    direction_icon = "\\U0001F7E2" if signal.direction.value == "BUY" else "\\U0001F534"
    payload = {
        "username": "TV Alert Relay",
        "embeds": [
            {
                "title": (
                    f"{direction_icon} {signal.direction.value} - "
                    f"{signal.symbol} ({signal.timeframe})"
                ),
                "fields": fields,
                "footer": {"text": signal.signal_key},
            }
        ],
    }
    return _post(webhook_url, payload, signal.signal_key)


def send_discord_trade_closed(webhook_url, trade):
    pnl_r = float(trade.get("pnl_r") or 0)
    direction_icon = "\\U0001F7E2" if pnl_r >= 0 else "\\U0001F534"
    payload = {
        "username": "TV Alert Relay",
        "embeds": [
            {
                "title": f"{direction_icon} Trade Closed - {trade['symbol']}",
                "fields": [
                    {
                        "name": "Direction",
                        "value": trade["direction"],
                        "inline": True,
                    },
                    {
                        "name": "Entry",
                        "value": str(trade["entry_price"]),
                        "inline": True,
                    },
                    {
                        "name": "Exit",
                        "value": str(trade["exit_price"]),
                        "inline": True,
                    },
                    {
                        "name": "Result",
                        "value": trade.get("exit_reason") or "CLOSED",
                        "inline": True,
                    },
                    {
                        "name": "PnL",
                        "value": (
                            f"{float(trade.get('pnl_pct') or 0):.2f}% | "
                            f"{pnl_r:.2f}R"
                        ),
                    },
                ],
                "footer": {"text": trade["signal_key"]},
            }
        ],
    }
    return _post(webhook_url, payload, trade["signal_key"])