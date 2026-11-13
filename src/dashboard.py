"""
Renders docs/index.html - a static dashboard GitHub Pages serves for free.
Regenerated every run from data/price_history.json, so it always reflects
the latest check. Settings (routes, destinations, thresholds) are managed
on docs/settings.html, not here.

Visual design follows a fixed dark-mode token set (status colors for deal
callouts, a validated 8-hue categorical set for airline accents) rather than
ad-hoc colors, so it stays consistent as more sections get added.
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

# Validated dark-mode categorical steps (fixed order - see the dataviz
# skill's reference palette). Used only as a decorative per-airline accent
# dot; the airline name itself is always shown as text alongside it, so the
# color never has to carry identity on its own.
CATEGORICAL = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"]

ANYWHERE_SHOWN_PER_ORIGIN = 8  # cap so "anywhere" doesn't turn into a wall of cards


def fmt_time(iso: str | None) -> str:
    if not iso:
        return "never"
    dt = datetime.fromisoformat(iso)
    return dt.strftime("%b %d, %Y %H:%M UTC")


def e(val) -> str:
    return html.escape(str(val)) if val is not None else ""


def airline_color(name: str | None) -> str:
    if not name:
        return "#898781"
    return CATEGORICAL[sum(ord(c) for c in name) % len(CATEGORICAL)]


def badge(label: str, kind: str) -> str:
    # kind: "good" (a real deal) or "best" (cheapest in its group)
    return f'<span class="badge {kind}">{"&#128293;" if kind == "good" else "&#11088;"} {e(label)}</span>'


def book_button(link: str | None) -> str:
    if not link:
        return '<span class="book-btn disabled">No link yet</span>'
    return f'<a class="book-btn" href="{e(link)}" target="_blank" rel="noopener noreferrer">Book / view fare &rarr;</a>'


def airline_chip(series: dict) -> str:
    name = series.get("last_airline")
    if not name:
        return ""
    dot_color = airline_color(name)
    flight_no = series.get("last_flightNumber")
    label = e(name) + (f" &middot; #{e(flight_no)}" if flight_no else "")
    return f'<span class="airline-chip"><span class="dot" style="background:{dot_color}"></span>{label}</span>'


def date_line(series: dict) -> str:
    dep = series.get("last_departureDate")
    ret = series.get("last_returnDate")
    if not dep:
        return ""
    line = f"Departs {e(dep)[:10]}"
    if ret:
        line += f" &middot; returns {e(ret)[:10]}"
    return f'<div class="dates">{line}</div>'


def route_card(cfg, origin, dest, series, threshold) -> str:
    labels = cfg.get("airports", {})
    o = e(labels.get(origin, {}).get("label", origin))
    d = e(labels.get(dest, {}).get("label", dest))
    samples = series.get("samples", [])
    last = series.get("last_price")
    min_seen = series.get("min_seen")
    avg_seen = series.get("avg_seen")
    canvas_id = f"chart-{origin}-{dest}"

    is_deal = threshold and last is not None and last <= threshold
    deal_badge = badge(f"At/under ${threshold:.0f} target", "good") if is_deal else ""

    if len(samples) >= 2:
        chart_data = json.dumps([s["price"] for s in samples])
        chart_labels = json.dumps([s["ts"][:10] for s in samples])
        chart_html = f"""
      <canvas id="{canvas_id}" height="54"></canvas>
      <script>
        new Chart(document.getElementById("{canvas_id}"), {{
          type: "line",
          data: {{ labels: {chart_labels}, datasets: [{{ data: {chart_data}, borderColor: "#3987e5", backgroundColor: "rgba(57,135,229,0.15)", fill: true, tension: 0.3, pointRadius: 0, borderWidth: 2 }}] }},
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
      <div class="card-tags">{deal_badge}{airline_chip(series)}</div>
      {date_line(series)}
      <div class="stats">
        <span>Lowest seen <b>${min_seen:.0f}</b></span>
        <span>Average <b>${avg_seen:.0f}</b></span>
      </div>
      {chart_html}
      <div class="card-foot">{book_button(series.get('last_link'))}</div>
    </div>
    """


def anywhere_group(cfg, origin, dests, max_price) -> str:
    labels = cfg.get("airports", {})
    o = e(labels.get(origin, {}).get("label", origin))
    ordered = sorted(dests.items(), key=lambda kv: kv[1].get("last_price", 9e9))
    shown, rest = ordered[:ANYWHERE_SHOWN_PER_ORIGIN], ordered[ANYWHERE_SHOWN_PER_ORIGIN:]

    cards = []
    for i, (dest, series) in enumerate(shown):
        last = series.get("last_price", 0)
        min_seen = series.get("min_seen", 0)
        avg_seen = series.get("avg_seen", 0)
        tags = []
        if i == 0:
            tags.append(badge("Best price here", "best"))
        if max_price and last <= max_price:
            tags.append(badge(f"At/under ${max_price:.0f} target", "good"))
        cards.append(f"""
        <div class="card small">
          <div class="card-head">
            <div class="route">{o} <span class="arrow">&rarr;</span> {e(dest)}</div>
            <div class="price">${last:.0f}</div>
          </div>
          <div class="card-tags">{''.join(tags)}{airline_chip(series)}</div>
          {date_line(series)}
          <div class="stats">
            <span>Lowest <b>${min_seen:.0f}</b></span>
            <span>Avg <b>${avg_seen:.0f}</b></span>
          </div>
          <div class="card-foot">{book_button(series.get('last_link'))}</div>
        </div>
        """)

    more_note = ""
    if rest:
        more_note = (
            f'<div class="more-note">+{len(rest)} more scanned from {o} - '
            f'<a href="settings.html">narrow this down to specific destinations</a> to see them all.</div>'
        )

    return f"""
    <div class="origin-group">
      <h3>From {o}</h3>
      <div class="grid">{''.join(cards)}</div>
      {more_note}
    </div>
    """


def alert_rows(history) -> str:
    rows = []
    for a in reversed(history.get("alerts", [])[-25:]):
        link = a.get("link")
        link_html = f'<a href="{e(link)}" target="_blank" rel="noopener noreferrer">view &rarr;</a>' if link else '<span class="muted">-</span>'
        rows.append(
            f"<tr><td>{fmt_time(a.get('ts'))}</td><td>{e(a.get('subject'))}</td>"
            f"<td class='num'>${a.get('price', 0):.0f}</td><td>{e(a.get('reason', ''))}</td><td>{link_html}</td></tr>"
        )
    return "\n".join(rows) if rows else "<tr><td colspan='5' class='muted center'>No alerts yet</td></tr>"


def hero_stats(cfg, history) -> str:
    route_prices = [s.get("last_price") for s in history.get("routes", {}).values() if s.get("last_price") is not None]
    anywhere_prices = [
        s.get("last_price")
        for dests in history.get("anywhere", {}).values()
        for s in dests.values()
        if s.get("last_price") is not None
    ]
    alert_count = len(history.get("alerts", []))

    tiles = [
        ("Cheapest tracked route", f"${min(route_prices):.0f}" if route_prices else "-"),
        ("Cheapest anywhere fare", f"${min(anywhere_prices):.0f}" if anywhere_prices else "-"),
        ("Deals alerted so far", str(alert_count)),
    ]
    return "".join(
        f'<div class="stat-tile"><div class="stat-label">{e(label)}</div><div class="stat-value">{e(val)}</div></div>'
        for label, val in tiles
    )


def main() -> None:
    with open(CONFIG_PATH) as f:
        cfg = json.load(f)
    history = storage.load()

    route_cards = []
    for route in cfg.get("routes", []):
        key = f"{route['origin']}-{route['destination']}"
        series = history["routes"].get(key)
        if series:
            route_cards.append(route_card(cfg, route["origin"], route["destination"], series, route.get("threshold_price")))

    max_price = (cfg.get("anywhere_scan") or {}).get("max_price")
    anywhere_groups = []
    for origin, dests in history.get("anywhere", {}).items():
        if dests:
            anywhere_groups.append(anywhere_group(cfg, origin, dests, max_price))

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
  :root {{
    color-scheme: dark;
    --page:#0d0d0d; --surface:#1a1a19; --surface-2:#202020;
    --ink:#f0efec; --ink-2:#c3c2b7; --muted:#898781;
    --border:rgba(255,255,255,0.10);
    --good:#0ca30c; --good-ink:#eafff0;
    --accent:#3987e5; --accent-2:#199e70;
    --radius:14px; --radius-sm:9px;
    --sp-1:4px; --sp-2:8px; --sp-3:12px; --sp-4:16px; --sp-5:20px; --sp-6:24px; --sp-7:32px; --sp-8:48px; --sp-9:64px;
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; font-family:"Inter",system-ui,-apple-system,"Segoe UI",sans-serif; background:var(--page); color:var(--ink); }}
  a {{ color:#7aa2ff; }}
  .num {{ font-variant-numeric: tabular-nums; }}

  header {{ position:relative; overflow:hidden; padding: var(--sp-8) var(--sp-7) var(--sp-6); border-bottom:1px solid var(--border); }}
  header::before {{
    content:""; position:absolute; inset:-40% -10% auto -10%; height:280px; pointer-events:none;
    background:
      radial-gradient(420px 220px at 12% 20%, rgba(57,135,229,0.22), transparent 70%),
      radial-gradient(360px 200px at 70% 10%, rgba(25,158,112,0.16), transparent 70%),
      radial-gradient(300px 180px at 92% 60%, rgba(213,81,129,0.12), transparent 70%);
  }}
  .header-row {{ position:relative; display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:var(--sp-4); max-width:1180px; margin:0 auto; }}
  h1 {{ margin:0 0 var(--sp-2); font-size:1.9rem; font-weight:800; letter-spacing:-0.02em; }}
  .sub {{ color:var(--muted); font-size:.88rem; }}
  nav a {{ text-decoration:none; color:var(--ink-2); background:var(--surface-2); border:1px solid var(--border); padding:10px 18px; border-radius:var(--radius-sm); font-size:.88rem; font-weight:600; transition:border-color .15s, color .15s; }}
  nav a:hover {{ border-color:var(--accent); color:#fff; }}

  .stat-row {{ position:relative; max-width:1180px; margin:var(--sp-7) auto 0; display:grid; grid-template-columns:repeat(auto-fit, minmax(180px,1fr)); gap:var(--sp-4); }}
  .stat-tile {{ background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); padding:var(--sp-5); }}
  .stat-label {{ color:var(--muted); font-size:.78rem; font-weight:600; text-transform:uppercase; letter-spacing:.04em; margin-bottom:var(--sp-2); }}
  .stat-value {{ font-size:1.7rem; font-weight:800; font-variant-numeric: tabular-nums; }}

  main {{ padding: var(--sp-8) var(--sp-7) var(--sp-9); max-width: 1180px; margin:0 auto; }}
  section + section {{ margin-top: var(--sp-9); }}
  h2 {{ font-size: 1.15rem; color:var(--ink); margin: 0 0 var(--sp-5); font-weight:700; letter-spacing:-0.01em; }}
  h3 {{ font-size: .95rem; color:var(--ink-2); margin: 0 0 var(--sp-4); font-weight:700; }}
  .origin-group + .origin-group {{ margin-top: var(--sp-7); }}

  .grid {{ display:grid; grid-template-columns: repeat(auto-fill, minmax(280px,1fr)); gap:var(--sp-5); }}
  .card {{ background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); padding:var(--sp-5); display:flex; flex-direction:column; gap:var(--sp-3); transition:transform .15s, box-shadow .15s, border-color .15s; }}
  .card:hover {{ transform:translateY(-2px); border-color:rgba(255,255,255,0.18); box-shadow:0 12px 24px -12px rgba(0,0,0,0.5); }}
  .card.small {{ padding:var(--sp-4); }}
  .card-head {{ display:flex; justify-content:space-between; align-items:baseline; gap:var(--sp-3); }}
  .route {{ font-weight:700; font-size:.98rem; }}
  .arrow {{ color:var(--accent); }}
  .price {{ font-size:1.5rem; font-weight:800; color:var(--ink); white-space:nowrap; font-variant-numeric: tabular-nums; }}
  .card-tags {{ display:flex; flex-wrap:wrap; gap:var(--sp-2); min-height:1px; }}
  .badge {{ display:inline-flex; align-items:center; gap:4px; font-size:.72rem; font-weight:700; padding:4px 9px; border-radius:999px; }}
  .badge.good {{ background:rgba(12,163,12,0.16); color:#6fe08c; border:1px solid rgba(12,163,12,0.35); }}
  .badge.best {{ background:rgba(201,133,0,0.16); color:#f0b23c; border:1px solid rgba(201,133,0,0.35); }}
  .airline-chip {{ display:inline-flex; align-items:center; gap:6px; font-size:.78rem; color:var(--ink-2); background:var(--surface-2); border:1px solid var(--border); padding:4px 9px 4px 7px; border-radius:999px; }}
  .airline-chip .dot {{ width:7px; height:7px; border-radius:50%; flex:none; }}
  .dates {{ font-size:.78rem; color:var(--muted); }}
  .stats {{ display:flex; gap:var(--sp-5); font-size:.82rem; color:var(--muted); }}
  .stats b {{ color:var(--ink-2); font-variant-numeric: tabular-nums; }}
  .chart-placeholder {{ font-size:.78rem; color:var(--muted); padding:var(--sp-3) 0; }}
  .card-foot {{ margin-top:auto; padding-top:var(--sp-1); }}
  .book-btn {{ display:inline-block; text-decoration:none; font-size:.82rem; font-weight:700; color:#06130c;
               background:linear-gradient(135deg,#1baf7a,#3987e5); padding:9px 15px; border-radius:var(--radius-sm); }}
  .book-btn:hover {{ filter:brightness(1.1); }}
  .book-btn.disabled {{ background:var(--surface-2); color:var(--muted); cursor:default; }}

  .more-note {{ margin-top:var(--sp-4); font-size:.82rem; color:var(--muted); }}

  table {{ width:100%; border-collapse: collapse; font-size:.86rem; }}
  th, td {{ text-align:left; padding:12px 14px; border-bottom:1px solid var(--border); }}
  th {{ color:var(--muted); font-weight:600; font-size:.76rem; text-transform:uppercase; letter-spacing:.03em; }}
  .muted {{ color:var(--muted); }}
  .center {{ text-align:center; }}
  .panel {{ background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); padding:var(--sp-2) var(--sp-5); overflow-x:auto; }}
  footer {{ max-width:1180px; margin:0 auto; padding:0 var(--sp-7) var(--sp-8); color:var(--muted); font-size:.8rem; }}
</style>
</head>
<body>
<header>
  <div class="header-row">
    <div>
      <h1>&#9992;&#65039; Flight Price Tracker</h1>
      <div class="sub">Last checked: {fmt_time(history.get('last_checked'))} &middot; fares from Travelpayouts/Aviasales, verify before booking</div>
    </div>
    <nav><a href="settings.html">&#9881;&#65039; Settings</a></nav>
  </div>
  <div class="stat-row">{hero_stats(cfg, history)}</div>
</header>
<main>
  <section>
    <h2>Tracked routes</h2>
    <div class="grid">
      {''.join(route_cards) if route_cards else '<div class="muted">No data yet - runs after the first scheduled check.</div>'}
    </div>
  </section>

  <section>
    <h2>Anywhere deals</h2>
    {''.join(anywhere_groups) if anywhere_groups else '<div class="muted">No data yet, or no origins configured for the anywhere scan - set them up on the Settings page.</div>'}
  </section>

  <section>
    <h2>Recent alerts</h2>
    <div class="panel">
    <table>
      <thead><tr><th>When</th><th>Alert</th><th>Price</th><th>Reason</th><th>Link</th></tr></thead>
      <tbody>
        {alert_rows(history)}
      </tbody>
    </table>
    </div>
  </section>
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
