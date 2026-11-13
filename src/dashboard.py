"""
Renders docs/index.html - a static dashboard GitHub Pages serves for free.
Regenerated every run from data/price_history.json, so it always reflects
the latest check.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config.json")
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "docs", "index.html")

import sys
sys.path.insert(0, os.path.dirname(__file__))
import storage  # noqa: E402


def fmt_time(iso: str | None) -> str:
    if not iso:
        return "never"
    dt = datetime.fromisoformat(iso)
    return dt.strftime("%b %d, %Y %H:%M UTC")


def route_card(cfg, origin, dest, series) -> str:
    labels = cfg.get("airports", {})
    o = labels.get(origin, {}).get("label", origin)
    d = labels.get(dest, {}).get("label", dest)
    samples = series.get("samples", [])
    last = series.get("last_price")
    min_seen = series.get("min_seen")
    avg_seen = series.get("avg_seen")
    chart_data = json.dumps([s["price"] for s in samples])
    chart_labels = json.dumps([s["ts"][:10] for s in samples])
    canvas_id = f"chart-{origin}-{dest}"
    return f"""
    <div class="card">
      <div class="card-head">
        <div class="route">{o} <span class="arrow">&rarr;</span> {d}</div>
        <div class="price">${last:.0f}</div>
      </div>
      <div class="stats">
        <span>Lowest seen: <b>${min_seen:.0f}</b></span>
        <span>Average: <b>${avg_seen:.0f}</b></span>
      </div>
      <canvas id="{canvas_id}" height="60"></canvas>
      <script>
        new Chart(document.getElementById("{canvas_id}"), {{
          type: "line",
          data: {{ labels: {chart_labels}, datasets: [{{ data: {chart_data}, borderColor: "#5b8def", backgroundColor: "rgba(91,141,239,0.15)", fill: true, tension: 0.3, pointRadius: 0 }}] }},
          options: {{ plugins: {{ legend: {{ display: false }} }}, scales: {{ x: {{ display: false }}, y: {{ display: false }} }}, responsive: true, maintainAspectRatio: false }}
        }});
      </script>
    </div>
    """


def anywhere_rows(cfg, origin, dests) -> str:
    labels = cfg.get("airports", {})
    o = labels.get(origin, {}).get("label", origin)
    rows = []
    for dest, series in sorted(dests.items(), key=lambda kv: kv[1].get("last_price", 9e9)):
        rows.append(
            f"<tr><td>{o}</td><td>{dest}</td><td>${series.get('last_price', 0):.0f}</td>"
            f"<td>${series.get('min_seen', 0):.0f}</td><td>${series.get('avg_seen', 0):.0f}</td></tr>"
        )
    return "\n".join(rows)


def alert_rows(history) -> str:
    rows = []
    for a in reversed(history.get("alerts", [])[-25:]):
        rows.append(
            f"<tr><td>{fmt_time(a.get('ts'))}</td><td>{a.get('subject')}</td>"
            f"<td>${a.get('price', 0):.0f}</td><td>{a.get('reason', '')}</td></tr>"
        )
    return "\n".join(rows) if rows else "<tr><td colspan='4' class='muted'>No alerts yet</td></tr>"


def main() -> None:
    with open(CONFIG_PATH) as f:
        cfg = json.load(f)
    history = storage.load()

    route_cards = []
    for route in cfg.get("routes", []):
        key = f"{route['origin']}-{route['destination']}"
        series = history["routes"].get(key)
        if series:
            route_cards.append(route_card(cfg, route["origin"], route["destination"], series))

    anywhere_tables = []
    for origin, dests in history.get("anywhere", {}).items():
        if not dests:
            continue
        anywhere_tables.append(anywhere_rows(cfg, origin, dests))

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Flight Price Tracker</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
  :root {{ color-scheme: dark; }}
  body {{ margin:0; font-family: -apple-system, Segoe UI, Roboto, sans-serif; background:#0f1115; color:#e8e9ec; }}
  header {{ padding: 28px 24px 12px; }}
  h1 {{ margin:0 0 4px; font-size: 1.6rem; }}
  .sub {{ color:#8a8f98; font-size: .9rem; }}
  main {{ padding: 8px 24px 48px; max-width: 1100px; margin:0 auto; }}
  h2 {{ font-size: 1.1rem; color:#c7cad1; margin: 32px 0 12px; }}
  .grid {{ display:grid; grid-template-columns: repeat(auto-fill, minmax(260px,1fr)); gap:16px; }}
  .card {{ background:#171a21; border:1px solid #262a33; border-radius:12px; padding:16px; }}
  .card-head {{ display:flex; justify-content:space-between; align-items:baseline; margin-bottom:8px; }}
  .route {{ font-weight:600; }}
  .arrow {{ color:#5b8def; }}
  .price {{ font-size:1.4rem; font-weight:700; color:#6fd08c; }}
  .stats {{ display:flex; gap:16px; font-size:.82rem; color:#9aa0ab; margin-bottom:8px; }}
  table {{ width:100%; border-collapse: collapse; font-size:.88rem; }}
  th, td {{ text-align:left; padding:8px 10px; border-bottom:1px solid #262a33; }}
  th {{ color:#8a8f98; font-weight:500; }}
  .muted {{ color:#565b66; text-align:center; }}
  .panel {{ background:#171a21; border:1px solid #262a33; border-radius:12px; padding:4px 16px; overflow-x:auto; }}
</style>
</head>
<body>
<header>
  <h1>✈️ Flight Price Tracker</h1>
  <div class="sub">Last checked: {fmt_time(history.get('last_checked'))} &middot; data from Amadeus, verify before booking</div>
</header>
<main>
  <h2>Tracked routes</h2>
  <div class="grid">
    {''.join(route_cards) if route_cards else '<div class="muted">No data yet - runs after the first scheduled check.</div>'}
  </div>

  <h2>Anywhere deals</h2>
  <div class="panel">
  <table>
    <thead><tr><th>From</th><th>To</th><th>Current</th><th>Lowest seen</th><th>Average</th></tr></thead>
    <tbody>
      {''.join(anywhere_tables) if anywhere_tables else '<tr><td colspan="5" class="muted">No data yet</td></tr>'}
    </tbody>
  </table>
  </div>

  <h2>Recent alerts</h2>
  <div class="panel">
  <table>
    <thead><tr><th>When</th><th>Alert</th><th>Price</th><th>Reason</th></tr></thead>
    <tbody>
      {alert_rows(history)}
    </tbody>
  </table>
  </div>
</main>
</body>
</html>
"""
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        f.write(html)
    print(f"[dashboard] wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
