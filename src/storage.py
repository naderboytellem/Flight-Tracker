"""
Flat-file price history, kept in data/price_history.json so it travels
with the git repo (committed by the GitHub Action after every run) and is
diffable / human-readable.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

HISTORY_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "price_history.json")

EMPTY = {
    "routes": {},     # "BNA-LAX" -> {"samples": [...], "min_seen": x, "avg_seen": x}
    "anywhere": {},    # "BNA" -> {"MCO": {"samples":[...], "min_seen":x, "avg_seen":x}, ...}
    "alerts": [],      # log of every alert sent
    "last_checked": None,
}

MAX_SAMPLES_PER_SERIES = 60  # keep history files small


def load() -> dict:
    if not os.path.exists(HISTORY_PATH):
        return json.loads(json.dumps(EMPTY))
    with open(HISTORY_PATH, "r") as f:
        return json.load(f)


def save(history: dict) -> None:
    os.makedirs(os.path.dirname(HISTORY_PATH), exist_ok=True)
    history["last_checked"] = datetime.now(timezone.utc).isoformat()
    with open(HISTORY_PATH, "w") as f:
        json.dump(history, f, indent=2, sort_keys=True)


def _update_series(series: dict, price: float, extra: dict) -> dict:
    series.setdefault("samples", [])
    series["samples"].append(
        {"ts": datetime.now(timezone.utc).isoformat(), "price": price, **extra}
    )
    series["samples"] = series["samples"][-MAX_SAMPLES_PER_SERIES:]
    prices = [s["price"] for s in series["samples"]]
    series["min_seen"] = min(prices)
    series["avg_seen"] = round(sum(prices) / len(prices), 2)
    series["last_price"] = price
    return series


def update_route(history: dict, origin: str, destination: str, price: float, extra: dict) -> dict:
    key = f"{origin}-{destination}"
    series = history["routes"].get(key, {})
    history["routes"][key] = _update_series(series, price, extra)
    return history["routes"][key]


def update_anywhere(history: dict, origin: str, destination: str, price: float, extra: dict) -> dict:
    history["anywhere"].setdefault(origin, {})
    series = history["anywhere"][origin].get(destination, {})
    history["anywhere"][origin][destination] = _update_series(series, price, extra)
    return history["anywhere"][origin][destination]


def log_alert(history: dict, alert: dict) -> None:
    alert = {"ts": datetime.now(timezone.utc).isoformat(), **alert}
    history.setdefault("alerts", [])
    history["alerts"].append(alert)
    history["alerts"] = history["alerts"][-200:]


def recent_alert_for(history: dict, subject: str, cooldown_hours: float) -> dict | None:
    """Most recent alert for this subject (route key or 'ORIGIN-DEST' anywhere pair) within cooldown."""
    now = datetime.now(timezone.utc)
    for alert in reversed(history.get("alerts", [])):
        if alert.get("subject") != subject:
            continue
        ts = datetime.fromisoformat(alert["ts"])
        if (now - ts).total_seconds() <= cooldown_hours * 3600:
            return alert
        break
    return None
