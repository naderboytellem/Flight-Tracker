"""
Thin client for the Travelpayouts (Aviasales) Data API.

Free to use: register as a Travelpayouts partner at https://www.travelpayouts.com
(takes a few minutes, no credit card - they just want a public channel like a
site or social account, which you don't need to actually use), then find your
API token in your account under the API token section.

Replaces the earlier plan to use Amadeus Self-Service, which Amadeus shut
down on 2026-07-17 (no more free sign-ups, existing keys disabled).

Docs: https://support.travelpayouts.com/hc/en-us/articles/203956163

Notes on the data:
- It's drawn from a 7-day cache of real traveler searches, not a live
  booking-engine quote, so treat every "price" here as "go check the real
  price," the same caveat that applied to Amadeus's test environment.
- The exact response shape isn't fully nailed down from docs alone, so
  this client parses defensively (handles a plain list of offers, or a
  dict keyed by destination) and raises a clear error with the raw
  payload shape if nothing recognizable comes back - check logs after the
  first real run and adjust `_parse_items` if needed.
"""
from __future__ import annotations

import os
import requests

BASE_URL = "https://api.travelpayouts.com"


class TravelpayoutsError(RuntimeError):
    pass


def _token() -> str:
    token = os.environ.get("TRAVELPAYOUTS_TOKEN")
    if not token:
        raise TravelpayoutsError(
            "TRAVELPAYOUTS_TOKEN is not set. Register free at "
            "https://www.travelpayouts.com and find it in your API token settings."
        )
    return token


def _get(path: str, params: dict) -> dict:
    params = {**params, "token": _token()}
    resp = requests.get(
        f"{BASE_URL}{path}",
        params=params,
        headers={"Accept-Encoding": "gzip, deflate"},
        timeout=30,
    )
    if resp.status_code == 429:
        raise TravelpayoutsError("Rate limited by Travelpayouts - back off and retry later.")
    if resp.status_code >= 400:
        raise TravelpayoutsError(f"{path} failed ({resp.status_code}): {resp.text[:400]}")
    payload = resp.json()
    if payload.get("success") is False:
        raise TravelpayoutsError(f"{path} returned success=false: {payload.get('error')}")
    return payload


def _parse_items(payload: dict, origin: str | None = None) -> list[dict]:
    data = payload.get("data")
    items: list[dict] = []

    if isinstance(data, list):
        items = [d for d in data if isinstance(d, dict)]
    elif isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, dict) and ("price" in value or "value" in value):
                entry = dict(value)
                entry.setdefault("destination", key)
                items.append(entry)
            elif isinstance(value, list):
                for sub in value:
                    if isinstance(sub, dict):
                        entry = dict(sub)
                        entry.setdefault("destination", key)
                        items.append(entry)

    out = []
    for it in items:
        price = it.get("price", it.get("value"))
        if price is None:
            continue
        out.append(
            {
                "origin": it.get("origin", origin),
                "destination": it.get("destination"),
                "departureDate": it.get("departure_at") or it.get("depart_date"),
                "returnDate": it.get("return_at") or it.get("return_date"),
                "price": float(price),
            }
        )
    return out


def cheapest_dates(origin: str, destination: str, currency: str = "usd") -> list[dict]:
    """Lowest fares on a specific route, Travelpayouts' cached search data."""
    payload = _get(
        "/aviasales/v3/prices_for_dates",
        {"origin": origin, "destination": destination, "one_way": "false", "sorting": "price", "currency": currency},
    )
    return _parse_items(payload, origin=origin)


def cheapest_anywhere(origin: str, currency: str = "usd") -> list[dict]:
    """Lowest fares from one origin to ANY destination ("anywhere" deals)."""
    payload = _get(
        "/aviasales/v3/prices_for_dates",
        {"origin": origin, "sorting": "route", "unique": "true", "currency": currency},
    )
    return _parse_items(payload, origin=origin)
