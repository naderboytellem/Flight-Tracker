"""
Renders docs/index.html - a static dashboard GitHub Pages serves for free.
Regenerated every run from data/price_history.json, so it always reflects
the latest check. Settings (routes, destinations, thresholds) are managed
on docs/settings.html, not here.
"""
from __future__ import annotations

import html
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


def e(val) -> str:
    return html.escape(str(val)) if val is not None else ""


def book_button(link: str | None) -> str:
    if not link:
        return '<span class="book-btn disabled">No link yet</span>'
    return f'<a class="book-btn" href="{e(link)}" target="_blank" rel="noopener noreferrer">Book / view fare &rarr;</a>'


def flight_meta(series: dict) -> str:
    bits = []
    if series.get("last_airline"):
        bits.append(e(series["last_airline"]))
    if series.get("last_flight_number"):
        bits.append(f"#{e(series['last_flight_number'])}")
    dep = series.get("last_departureDate")
    ret = series.get("last_returnDate")
    if dep:
        date_bit = f"Departs {e(dep)[:10]}"
        if ret:
            date_bit += f" &middot; returns {e(ret)[:10]}"
        bits.append(date_bit)
    return " &nbsp;&bull;&nbsp; ".join(bits) if bits else '<span class="muted">No flight details yet</span>'


def route_card(cfg, origin, dest, series) -> str:
    labels = cfg.get("airports", {})
    o = e(labels.get(origin, {}).get("label", origin))
    d = e(labels.get(dest, {}).get("label", dest))
    samples = series.get("samples", [])
    last = series.get("last_price")
    min_seen = series.get("min_seen")
    avg_seen = series.get("avg_seen")
    canvas_id = f"chart-{origin}-{dest}"

    if len(samples) >= 2:
        chart_data = json.dumps([s["price"] for s in samples])
        chart_labels = json.dumps([s["ts"][:10] for s in samples])
        chart_html = f"""
      <canvas id="{canvas_id}" height="60"></canvas>
      <script>
        new Chart(document.getElementById("{canvas_id}"), {{
          type: "line",
          data: {{ labels: {chart_labels}, datasets: [{{ data: {chart_data}, borderColor: "#5b8def", backgroundColor: "rgba(91,141,239,0.15)", fill: true, tension: 0.3, pointRadius: 0 }}] }},
          options: {{ plugins: {{ legend: {{ display: false }} }}, scales: {{ x: {{ display: false }}, y: {{ display: false }} }}, responsive: true, maintainAspectRatio: false }}
        }});
      </script>"""
    else:
        chart_html = '<div class="chart-placeholder">Tracking price history - check back after the next run.</div>'

    return f"""
    <div class="card">
      <div class="card-head">
        <div class="route">{o} <span class="arrow">&rarr;</span> {d}</div>
        <div class="price">${last:.0f}</div>
      </div>
      <div class="meta">{flight_meta(series)}</div>
      <div class="stats">
        <span>Lowest seen <b>${min_seen:.0f}</b></span>
        <span>Average <b>${avg_seen:.0f}</b></span>
      </div>
      {chart_html}
      <div class="card-foot">{book_button(series.get('last_link'))}</div>
    </div>
    """


def anywhere_card(cfg, origin, dest, series) -> str:
    labels = cfg.get("airports", {})
    o = e(labels.get(origin, {}).get("label", origin))
    last = series.get("last_price", 0)
    min_seen = series.get("min_seen", 0)
    avg_seen = series.get("avg_seen", 0)
    return f"""
    <div class="card small">
      <div class="card-head">
        <div class="route">{o} <span class="arrow">&rarr;</span> {e(dest)}</div>
        <div class="price">${last:.0f}</div>
      </div>
      <div class="meta">{flight_meta(series)}</div>
      <div class="stats">
        <span>Lowest <b>${min_seen:.0f}</b></span>
        <span>Avg <b>${avg_seen:.0f}</b></span>
      </div>
      <div class="card-foot">{book_button(series.get('last_link'))}</div>
    </div>
    """


def alert_rows(history) -> str:
    rows = []
    for a in reversed(history.get("alerts", [])[-25:]):
        link = a.get("link")
        link_html = f'<a href="{e(link)}" target="_blank" rel="noopener noreferrer">view &rarr;</a>' if link else '<span class="muted">-</span>'
        rows.append(
            f"<tr><td>{fmt_time(a.get('ts'))}</td><td>{e(a.get('subject'))}</td>"
            f"<td>${a.get('price', 0):.0f}</td><td>{e(a.get('reason', ''))}</td><td>{link_html}</td></tr>"
        )
    return "\n".join(rows) if rows else "<tr><td colspan='5' class='muted'>No alerts yet</td></tr>"


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

    anywhere_cards = []
    for origin, dests in history.get("anywhere", {}).items():
        for dest, series in sorted(dests.items(), key=lambda kv: kv[1].get("last_price", 9e9)):
            anywhere_cards.append(anywhere_card(cfg, origin, dest, series))

    html_out = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Flight Price Tracker</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
  :root {{ color-scheme: dark; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; font-family: "Inter", -apple-system, Segoe UI, Roboto, sans-serif; background:#0b0d12; color:#e8e9ec; }}
  a {{ color:#7aa2ff; }}
  header {{ padding: 28px 28px 16px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px;
            background:linear-gradient(135deg, rgba(91,141,239,0.12), transparent 60%); border-bottom:1px solid #1c2029; }}
  .title h1 {{ margin:0 0 4px; font-size: 1.7rem; font-weight:800; letter-spacing:-0.02em; }}
  .sub {{ color:#8a8f98; font-size: .88rem; }}
  nav a {{ text-decoration:none; color:#c7cad1; background:#171a21; border:1px solid #262a33; padding:9px 16px; border-radius:9px; font-size:.88rem; font-weight:600; }}
  nav a:hover {{ border-color:#5b8def; color:#fff; }}
  main {{ padding: 8px 28px 56px; max-width: 1200px; margin:0 auto; }}
  h2 {{ font-size: 1.05rem; color:#c7cad1; margin: 36px 0 14px; font-weight:700; letter-spacing:-0.01em; }}
  .grid {{ display:grid; grid-template-columns: repeat(auto-fill, minmax(270px,1fr)); gap:16px; }}
  .card {{ background:#12151c; border:1px solid #20242e; border-radius:14px; padding:18px; display:flex; flex-direction:column; gap:10px; }}
  .card.small {{ padding:16px; }}
  .card-head {{ display:flex; justify-content:space-between; align-items:baseline; gap:10px; }}
  .route {{ font-weight:700; font-size:.98rem; }}
  .arrow {{ color:#5b8def; }}
  .price {{ font-size:1.45rem; font-weight:800; color:#6fd08c; white-space:nowrap; }}
  .meta {{ font-size:.78rem; color:#9aa0ab; min-height:1.1em; }}
  .stats {{ display:flex; gap:18px; font-size:.82rem; color:#9aa0ab; }}
  .stats b {{ color:#dfe1e6; }}
  .chart-placeholder {{ font-size:.78rem; color:#565b66; padding:14px 0; }}
  .card-foot {{ margin-top:auto; padding-top:4px; }}
  .book-btn {{ display:inline-block; text-decoration:none; font-size:.82rem; font-weight:700; color:#0b0d12;
               background:linear-gradient(135deg,#6fd08c,#5b8def); padding:8px 14px; border-radius:8px; }}
  .book-btn:hover {{ filter:brightness(1.08); }}
  .book-btn.disabled {{ background:#1c2029; color:#565b66; cursor:default; }}
  table {{ width:100%; border-collapse: collapse; font-size:.86rem; }}
  th, td {{ text-align:left; padding:10px 12px; border-bottom:1px solid #20242e; }}
  th {{ color:#8a8f98; font-weight:600; }}
  .muted {{ color:#565b66; }}
  td.muted {{ text-align:center; }}
  .panel {{ background:#12151c; border:1px solid #20242e; border-radius:14px; padding:4px 16px; overflow-x:auto; }}
  footer {{ max-width:1200px; margin:0 auto; padding:0 28px 48px; color:#565b66; font-size:.8rem; }}
</style>
</head>
<body>
<header>
  <div class="title">
    <h1>&#9992;&#65039; Flight Price Tracker</h1>
    <div class="sub">Last checked: {fmt_time(history.get('last_checked'))} &middot; fares from Travelpayouts/Aviasales, verify before booking</div>
  </div>
  <nav><a href="settings.html">&#9881;&#65039; Settings</a></nav>
</header>
<main>
  <h2>Tracked routes</h2>
  <div class="grid">
    {''.join(route_cards) if route_cards else '<div class="muted">No data yet - runs after the first scheduled check.</div>'}
  </div>

  <h2>Anywhere deals</h2>
  <div class="grid">
    {''.join(anywhere_cards) if anywhere_cards else '<div class="muted">No data yet, or no destinations configured for the anywhere scan - set them up on the Settings page.</div>'}
  </div>

  <h2>Recent alerts</h2>
  <div class="panel">
  <table>
    <thead><tr><th>When</th><th>Alert</th><th>Price</th><th>Reason</th><th>Link</th></tr></thead>
    <tbody>
      {alert_rows(history)}
    </tbody>
  </table>
  </div>
</main>
<footer>Prices are cached search data, not live quotes - always confirm on the airline/OTA page before buying.</footer>
</body>
</html>
"""
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        f.write(html_out)
    print(f"[dashboard] wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
