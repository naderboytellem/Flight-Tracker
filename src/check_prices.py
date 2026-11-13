"""
Main entry point - run on a schedule (see .github/workflows/check-prices.yml).

For each configured route and each "anywhere" origin:
  1. Pull the current cheapest price from Amadeus.
  2. Compare it to what we've historically seen for that route/destination.
  3. If it's a deal (under your threshold, or a big drop vs. its own
     history), send an email + push alert, with a cooldown so you don't
     get the same alert every 6 hours.
  4. Always record the sample, so the dashboard has history to chart even
     when nothing is alert-worthy.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import travelpayouts_client as flight_client  # noqa: E402
import airlines  # noqa: E402
import alerts  # noqa: E402
import storage  # noqa: E402

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config.json")

# Safety valve: never send more than this many alerts in a single run, no
# matter what the data says. Protects against exactly the kind of flood a
# loose "anywhere" threshold (or any future bug) could otherwise cause.
MAX_ALERTS_PER_RUN = 8


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return json.load(f)


def airport_label(cfg: dict, code: str) -> str:
    return cfg.get("airports", {}).get(code, {}).get("label", code)


class AlertBudget:
    """Caps total alerts sent in one run, and flags a cold-start history so
    the very first run (no baseline yet) only seeds data silently instead
    of treating every result as a brand-new deal."""

    def __init__(self, history: dict, limit: int = MAX_ALERTS_PER_RUN):
        self.is_first_run = not history.get("routes") and not any(
            history.get("anywhere", {}).values()
        )
        self.remaining = limit

    def may_fire(self) -> bool:
        if self.is_first_run:
            return False
        if self.remaining <= 0:
            return False
        self.remaining -= 1
        return True


def check_routes(cfg: dict, history: dict, budget: "AlertBudget") -> None:
    rules = cfg.get("deal_rules", {})
    cooldown = rules.get("realert_cooldown_hours", 24)

    for route in cfg.get("routes", []):
        origin, dest = route["origin"], route["destination"]
        key = f"{origin}-{dest}"
        try:
            fares = flight_client.cheapest_dates(origin, dest)
        except flight_client.TravelpayoutsError as exc:
            print(f"[routes] {key}: ERROR {exc}")
            continue

        if not fares:
            print(f"[routes] {key}: no fares returned")
            continue

        best = min(fares, key=lambda f: f["price"])
        prior_min = history["routes"].get(key, {}).get("min_seen")
        prior_avg = history["routes"].get(key, {}).get("avg_seen")

        series = storage.update_route(
            history, origin, dest, best["price"],
            {
                "departureDate": best.get("departureDate"),
                "returnDate": best.get("returnDate"),
                "link": best.get("link"),
                "airline": airlines.get_airline_name(best.get("airline")),
                "flightNumber": best.get("flightNumber"),
            },
        )

        threshold = route.get("threshold_price")
        is_deal = False
        reason = ""

        if threshold and best["price"] <= threshold:
            is_deal, reason = True, f"at/under your ${threshold} target"
        elif prior_min and best["price"] <= prior_min * (1 - rules.get("drop_below_historical_min_pct", 10) / 100):
            is_deal, reason = True, f"a new low vs. the ${prior_min} previously seen"
        elif prior_avg and best["price"] <= prior_avg * (1 - rules.get("drop_below_historical_avg_pct", 20) / 100):
            is_deal, reason = True, f"well below the recent average (${prior_avg})"

        print(f"[routes] {key}: ${best['price']} (deal={is_deal}) min_seen={series.get('min_seen')}")

        if is_deal:
            already = storage.recent_alert_for(history, key, cooldown)
            if already:
                print(f"[routes] {key}: deal held off, alerted {already['ts']} already")
                continue
            if not budget.may_fire():
                reason_skip = "first run (building baseline)" if budget.is_first_run else "per-run alert cap hit"
                print(f"[routes] {key}: deal held off, {reason_skip}")
                continue
            o_label, d_label = airport_label(cfg, origin), airport_label(cfg, dest)
            fire_route_alert(o_label, d_label, origin, dest, best, reason)
            storage.log_alert(history, {
                "subject": key, "type": "route", "price": best["price"], "reason": reason,
                "link": best.get("link"),
            })


def fire_route_alert(o_label, d_label, origin, dest, fare, reason) -> None:
    subject = f"✈️ {o_label} → {d_label}: ${fare['price']:.0f}"
    airline_name = airlines.get_airline_name(fare.get("airline"))
    body = (
        f"{o_label} ({origin}) to {d_label} ({dest})\n"
        f"${fare['price']:.0f} round trip, departing {fare.get('departureDate')}"
        + (f", returning {fare.get('returnDate')}" if fare.get("returnDate") else "")
        + (f"\nAirline: {airline_name}" if airline_name else "")
        + f"\n\nWhy you're seeing this: {reason}.\n"
        "Double-check the live price before booking - this is a snapshot, not a live quote.\n"
        + (f"\nBook / view: {fare.get('link')}" if fare.get("link") else "")
    )
    alerts.fire(subject, body, url=fare.get("link") or None)


def check_anywhere(cfg: dict, history: dict, budget: "AlertBudget") -> None:
    scan = cfg.get("anywhere_scan")
    if not scan:
        return
    rules = cfg.get("deal_rules", {})
    cooldown = rules.get("realert_cooldown_hours", 24)
    max_price = scan.get("max_price")
    # Optional allow-list of destination IATA codes, e.g. ["MIA","CUN","LAS"].
    # Empty/absent = truly "anywhere", like Going.com. Set via config.json or
    # the Settings page.
    wanted_destinations = {d.upper() for d in scan.get("destinations", []) if d}

    for origin in scan.get("origins", []):
        try:
            fares = flight_client.cheapest_anywhere(origin)  # pull broadly, filter ourselves
        except flight_client.TravelpayoutsError as exc:
            print(f"[anywhere] {origin}: ERROR {exc}")
            continue

        o_label = airport_label(cfg, origin)
        checked = 0
        for fare in fares:
            dest = fare["destination"]
            if wanted_destinations and dest and dest.upper() not in wanted_destinations:
                continue
            checked += 1
            key = f"{origin}-{dest}"
            prior = history["anywhere"].get(origin, {}).get(dest, {})
            prior_min, prior_avg = prior.get("min_seen"), prior.get("avg_seen")

            series = storage.update_anywhere(
                history, origin, dest, fare["price"],
                {
                    "departureDate": fare.get("departureDate"),
                    "returnDate": fare.get("returnDate"),
                    "link": fare.get("link"),
                    "airline": airlines.get_airline_name(fare.get("airline")),
                    "flightNumber": fare.get("flightNumber"),
                },
            )

            is_deal, reason = False, ""
            if max_price and fare["price"] <= max_price:
                is_deal, reason = True, f"at/under your ${max_price} anywhere target"
            elif prior_min and fare["price"] <= prior_min * (1 - rules.get("drop_below_historical_min_pct", 10) / 100):
                is_deal, reason = True, f"a new low vs. the ${prior_min} previously seen"
            elif prior_avg and fare["price"] <= prior_avg * (1 - rules.get("drop_below_historical_avg_pct", 20) / 100):
                is_deal, reason = True, f"well below the recent average (${prior_avg})"

            if is_deal:
                already = storage.recent_alert_for(history, key, cooldown)
                if already:
                    continue
                if not budget.may_fire():
                    reason_skip = "first run (building baseline)" if budget.is_first_run else "per-run alert cap hit"
                    print(f"[anywhere] {key}: deal held off, {reason_skip}")
                    continue
                subject = f"🔥 Deal from {o_label}: {dest} for ${fare['price']:.0f}"
                airline_name = airlines.get_airline_name(fare.get("airline"))
                body = (
                    f"{o_label} ({origin}) → {dest}\n"
                    f"${fare['price']:.0f} round trip, departing {fare.get('departureDate')}"
                    + (f", returning {fare.get('returnDate')}" if fare.get("returnDate") else "")
                    + (f"\nAirline: {airline_name}" if airline_name else "")
                    + f"\n\nWhy you're seeing this: {reason}.\n"
                    "Double-check the live price before booking - this is a snapshot, not a live quote.\n"
                    + (f"\nBook / view: {fare.get('link')}" if fare.get("link") else "")
                )
                alerts.fire(subject, body, url=fare.get("link") or None)
                storage.log_alert(history, {
                    "subject": key, "type": "anywhere", "price": fare["price"], "reason": reason,
                    "link": fare.get("link"),
                })

        print(f"[anywhere] {origin}: scanned {checked}/{len(fares)} destinations"
              + (" (filtered to your destination list)" if wanted_destinations else ""))


def main() -> None:
    cfg = load_config()
    history = storage.load()
    budget = AlertBudget(history)
    if budget.is_first_run:
        print("[check_prices] first run detected - building baseline, no alerts will be sent this run")

    check_routes(cfg, history, budget)
    check_anywhere(cfg, history, budget)

    storage.save(history)
    print("[check_prices] done")


if __name__ == "__main__":
    main()
