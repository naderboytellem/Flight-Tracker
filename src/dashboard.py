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
      <div class="chart-wrap"><canvas id="{canvas_id}"></canvas></div>
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
        airline_name = series.get("last_airline") or ""
        cards.append(f"""
        <div class="card small" data-origin="{e(origin)}" data-dest="{e(dest)}" data-airline="{e(airline_name)}">
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
            f'<a href="#" onclick="ftOpenManage(\'dest-input\'); return false;">narrow this down to specific destinations</a> to see them all.</div>'
        )

    return f"""
    <div class="origin-group">
      <h3>From {o}</h3>
      <div class="grid">{''.join(cards)}</div>
      {more_note}
    </div>
    """


def filter_bar_html(airlines: list[str]) -> str:
    if not airlines:
        return ""
    pills = "".join(
        f'<button type="button" class="airline-pill" data-airline="{e(name)}" '
        f'onclick="this.classList.toggle(\'active\'); ftApplyFilters();">'
        f'<span class="dot" style="background:{airline_color(name)}"></span>{e(name)}</button>'
        for name in airlines
    )
    return f"""
    <div class="filter-bar">
      <input type="text" id="ft-dest-search" placeholder="Search destination (e.g. MIA, Miami)" oninput="ftApplyFilters()">
      <div class="pill-row">{pills}</div>
      <button type="button" class="filter-clear" onclick="ftClearFilters()">Clear filters</button>
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


MANAGE_PANEL = r"""
<style>
  #manage-panel { max-height:0; opacity:0; overflow:hidden; transition:max-height .35s ease, opacity .25s ease; }
  #manage-panel.mp-open { max-height:4000px; opacity:1; }
  .mp-inner { max-width:1180px; margin:0 auto; padding:0 32px 40px; }
  .mp-panel { background:#12151c; border:1px solid #20242e; border-radius:14px; padding:20px 22px; margin-top:20px; }
  .mp-panel h2 { margin:0 0 4px; font-size:1.05rem; font-weight:700; color:#f0efec; }
  .mp-hint { margin:4px 0 16px; color:#8a8f98; font-size:.85rem; line-height:1.5; }
  .mp-panel label { display:block; font-size:.78rem; color:#9aa0ab; font-weight:600; margin-bottom:5px; }
  .mp-panel input[type=text], .mp-panel input[type=password], .mp-panel input[type=number] {
    width:100%; background:#0b0d12; border:1px solid #262a33; color:#e8e9ec; border-radius:8px;
    padding:9px 11px; font-size:.9rem; font-family:inherit;
  }
  .mp-panel input:focus { outline:none; border-color:#5b8def; }
  .mp-row { display:flex; gap:12px; flex-wrap:wrap; }
  .mp-row > div { flex:1; min-width:140px; }
  .mp-field { margin-bottom:14px; }
  .mp-panel button { font-family:inherit; cursor:pointer; border:none; border-radius:8px; font-weight:700; font-size:.85rem; padding:10px 16px; }
  .mp-btn-primary { background:linear-gradient(135deg,#6fd08c,#5b8def); color:#0b0d12; }
  .mp-btn-primary:hover { filter:brightness(1.08); }
  .mp-btn-secondary { background:#1c2029; color:#dfe1e6; border:1px solid #2b303c; }
  .mp-btn-secondary:hover { border-color:#5b8def; }
  .mp-btn-icon { background:#1c2029; color:#dfe1e6; border:1px solid #2b303c; padding:6px 10px; font-size:.8rem; }
  .mp-panel table { width:100%; border-collapse:collapse; font-size:.86rem; margin-bottom:10px; }
  .mp-panel th, .mp-panel td { text-align:left; padding:8px 8px; border-bottom:1px solid #20242e; vertical-align:middle; }
  .mp-panel th { color:#8a8f98; font-weight:600; font-size:.78rem; }
  .mp-panel td input { padding:7px 9px; }
  .mp-chip-box { display:flex; flex-wrap:wrap; gap:6px; padding:8px; border:1px solid #262a33; border-radius:8px; background:#0b0d12; min-height:42px; align-items:center; }
  .mp-chip { background:#1c2029; border:1px solid #2b303c; color:#dfe1e6; padding:5px 8px; border-radius:6px; font-size:.82rem; display:flex; align-items:center; gap:6px; }
  .mp-chip button { background:none; padding:0; font-size:.9rem; color:#8a8f98; border-radius:0; }
  .mp-chip-box input { border:none; background:none; flex:1; min-width:120px; padding:4px; }
  .mp-chip-box input:focus { outline:none; }
  .mp-check-row { display:flex; gap:16px; flex-wrap:wrap; }
  .mp-check-row label { display:flex; align-items:center; gap:6px; font-size:.86rem; color:#dfe1e6; font-weight:500; margin:0; }
  .mp-check-row input[type=checkbox] { width:auto; }
  .mp-status { font-size:.82rem; border-radius:8px; padding:10px 12px; margin-top:10px; display:none; }
  .mp-status.ok { display:block; background:#10251a; color:#8ce0ab; border:1px solid #1c3a28; }
  .mp-status.err { display:block; background:#2a1620; color:#f08a9c; border:1px solid #3a1c28; }
  .mp-status.info { display:block; background:#13202f; color:#8fc0f0; border:1px solid #1c3347; }
  .mp-actions-bar { position:sticky; bottom:0; background:#0b0d12cc; backdrop-filter:blur(6px); border-top:1px solid #1c2029; padding:14px 0; display:flex; gap:10px; margin-top:10px; flex-wrap:wrap; align-items:center; }
  .mp-muted { color:#565b66; font-size:.82rem; }
  .mp-badge { display:inline-block; font-size:.72rem; font-weight:700; padding:3px 8px; border-radius:999px; margin-left:8px; }
  .mp-badge.connected { background:#10251a; color:#8ce0ab; }
  .mp-badge.disconnected { background:#2a1620; color:#f08a9c; }
  .mp-panel details summary { cursor:pointer; color:#7aa2ff; font-size:.85rem; margin-bottom:8px; }
</style>
<div id="manage-panel">
  <div class="mp-inner">

    <div class="mp-panel">
      <h2>&#9881;&#65039; Manage this tracker <span id="conn-badge" class="mp-badge disconnected">Not connected</span></h2>
      <p class="mp-hint">
        This talks directly to GitHub's API from your browser - no server in between, nothing sent anywhere except api.github.com.
        You'll need a personal access token so it's allowed to read and update <code>config.json</code> (and optionally trigger a check).
      </p>
      <details>
        <summary>How do I get a token?</summary>
        <p class="mp-hint">
          1. Go to <a href="https://github.com/settings/personal-access-tokens/new" target="_blank" rel="noopener noreferrer">github.com/settings/personal-access-tokens/new</a> (fine-grained tokens).<br>
          2. Under "Repository access," choose "Only select repositories" and pick this repo.<br>
          3. Under "Permissions" &rarr; "Repository permissions," set <b>Contents</b> to "Read and write." For the "Run a check now" button too, also set <b>Actions</b> to "Read and write."<br>
          4. Generate the token and paste it below. It's saved only in this browser (localStorage) - never shared, never sent anywhere but GitHub.
        </p>
      </details>
      <div class="mp-row">
        <div class="mp-field">
          <label for="repo">Repository</label>
          <input type="text" id="repo" placeholder="yourname/Flight-Tracker" value="naderboytellem/Flight-Tracker">
        </div>
        <div class="mp-field">
          <label for="token">Personal access token</label>
          <input type="password" id="token" placeholder="github_pat_...">
        </div>
      </div>
      <div class="mp-row">
        <button class="mp-btn-primary" id="btn-connect">Connect &amp; load settings</button>
        <button class="mp-btn-secondary" id="btn-forget">Forget token on this device</button>
      </div>
      <div id="status-connect" class="mp-status"></div>
    </div>

    <div id="form-wrap" style="display:none;">

      <div class="mp-panel">
        <h2>Airports you fly from</h2>
        <p class="mp-hint">These show up as choices everywhere below.</p>
        <table id="tbl-airports">
          <thead><tr><th style="width:100px">Code</th><th>Name</th><th style="width:40px"></th></tr></thead>
          <tbody></tbody>
        </table>
        <button class="mp-btn-secondary" id="btn-add-airport">+ Add airport</button>
      </div>

      <div class="mp-panel">
        <h2>Specific routes to watch</h2>
        <p class="mp-hint">Exact A&rarr;B routes you care about, with your own target price for each.</p>
        <table id="tbl-routes">
          <thead><tr><th>From</th><th>To</th><th style="width:140px">Alert below $</th><th style="width:40px"></th></tr></thead>
          <tbody></tbody>
        </table>
        <button class="mp-btn-secondary" id="btn-add-route">+ Add route</button>
      </div>

      <div class="mp-panel">
        <h2>Anywhere deals</h2>
        <p class="mp-hint">Scans from your chosen airports for cheap fares. Leave destinations empty to scan truly anywhere (like Going.com), or list specific places to only watch those.</p>
        <div class="mp-field">
          <label>Scan from</label>
          <div id="anywhere-origins" class="mp-check-row"></div>
        </div>
        <div class="mp-field">
          <label for="max-price">Alert when a fare is at or under</label>
          <input type="number" id="max-price" style="max-width:160px">
        </div>
        <div class="mp-field">
          <label>Destinations to watch (leave empty for anywhere)</label>
          <div class="mp-chip-box" id="dest-chips">
            <input type="text" id="dest-input" placeholder="Type an airport code (e.g. MIA) and press Enter">
          </div>
          <p class="mp-hint" style="margin-bottom:0;">Use 3-letter IATA airport codes - e.g. MIA (Miami), CUN (Canc&uacute;n), LAS (Las Vegas), JFK (New York).</p>
        </div>
      </div>

      <div class="mp-panel">
        <h2>Deal sensitivity</h2>
        <p class="mp-hint">Beyond your set prices above, also alert on drops relative to a route's own history.</p>
        <div class="mp-row">
          <div class="mp-field">
            <label for="pct-min">New low vs. lowest ever seen (%)</label>
            <input type="number" id="pct-min">
          </div>
          <div class="mp-field">
            <label for="pct-avg">Below the recent average (%)</label>
            <input type="number" id="pct-avg">
          </div>
          <div class="mp-field">
            <label for="cooldown">Don't repeat the same alert for (hours)</label>
            <input type="number" id="cooldown">
          </div>
        </div>
      </div>

      <div class="mp-actions-bar">
        <button class="mp-btn-primary" id="btn-save">Save settings</button>
        <button class="mp-btn-secondary" id="btn-run-now">Run a check now</button>
        <span class="mp-muted">Saves go live next run (every 6h), or immediately via Run a check now.</span>
      </div>
      <div id="status-save" class="mp-status"></div>
    </div>

  </div>
</div>
<script>
const API = "https://api.github.com";
let currentSha = null;
let config = null;
let checkedOrigins = new Set();

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "text") node.textContent = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v);
  }
  children.forEach(c => node.appendChild(c));
  return node;
}

function showStatus(id, kind, msg) {
  const box = document.getElementById(id);
  box.className = "mp-status " + kind;
  box.textContent = msg;
}

function getCreds() {
  return {
    repo: document.getElementById("repo").value.trim(),
    token: document.getElementById("token").value.trim(),
  };
}

function saveCredsLocally(repo, token) {
  localStorage.setItem("ft_repo", repo);
  localStorage.setItem("ft_token", token);
}

function loadCredsFromStorage() {
  const repo = localStorage.getItem("ft_repo");
  const token = localStorage.getItem("ft_token");
  if (repo) document.getElementById("repo").value = repo;
  if (token) document.getElementById("token").value = token;
  return { repo, token };
}

function b64EncodeUnicode(str) {
  return btoa(encodeURIComponent(str).replace(/%([0-9A-F]{2})/g, (_, p1) => String.fromCharCode('0x' + p1)));
}
function b64DecodeUnicode(str) {
  return decodeURIComponent(atob(str.replace(/\n/g, '')).split('').map(c =>
    '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2)
  ).join(''));
}

async function ghRequest(path, options = {}) {
  const { token } = getCreds();
  const resp = await fetch(API + path, {
    ...options,
    headers: {
      "Authorization": "Bearer " + token,
      "Accept": "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      ...(options.headers || {}),
    },
  });
  return resp;
}

async function loadConfig() {
  const { repo, token } = getCreds();
  if (!repo || !token) {
    showStatus("status-connect", "err", "Enter both a repository and a token first.");
    return;
  }
  showStatus("status-connect", "info", "Loading config.json...");
  try {
    const resp = await ghRequest(`/repos/${repo}/contents/config.json`);
    if (resp.status === 401) throw new Error("That token was rejected (401) - check it's correct and not expired.");
    if (resp.status === 404) throw new Error("Couldn't find config.json in that repo (404) - check the repo name.");
    if (!resp.ok) throw new Error(`GitHub returned ${resp.status}: ${await resp.text()}`);
    const data = await resp.json();
    currentSha = data.sha;
    config = JSON.parse(b64DecodeUnicode(data.content));
    saveCredsLocally(repo, token);
    document.getElementById("conn-badge").textContent = "Connected";
    document.getElementById("conn-badge").className = "mp-badge connected";
    document.getElementById("form-wrap").style.display = "block";
    renderForm();
    showStatus("status-connect", "ok", "Loaded current settings from GitHub.");
  } catch (err) {
    document.getElementById("conn-badge").textContent = "Not connected";
    document.getElementById("conn-badge").className = "mp-badge disconnected";
    document.getElementById("form-wrap").style.display = "none";
    showStatus("status-connect", "err", err.message);
  }
}

function renderForm() {
  renderAirports();
  renderRoutes();
  renderAnywhere();
  const rules = config.deal_rules || {};
  document.getElementById("pct-min").value = rules.drop_below_historical_min_pct ?? 10;
  document.getElementById("pct-avg").value = rules.drop_below_historical_avg_pct ?? 20;
  document.getElementById("cooldown").value = rules.realert_cooldown_hours ?? 24;
}

function renderAirports() {
  const tbody = document.querySelector("#tbl-airports tbody");
  tbody.innerHTML = "";
  checkedOrigins = new Set((config.anywhere_scan || {}).origins || []);
  const airports = config.airports || {};
  Object.entries(airports).forEach(([code, info]) => {
    addAirportRow(code, info.label || "");
  });
}

function onAirportsChanged() {
  renderAnywhereOriginChecks();
  refreshRouteOriginSelects();
}

function refreshRouteOriginSelects() {
  const rows = getAirportRows();
  document.querySelectorAll("#tbl-routes select").forEach(sel => {
    const current = sel.value;
    sel.innerHTML = "";
    rows.forEach(a => {
      const opt = el("option", { value: a.code, text: `${a.code} - ${a.label || a.code}` });
      if (a.code === current) opt.setAttribute("selected", "selected");
      sel.appendChild(opt);
    });
  });
}

function addAirportRow(code = "", label = "") {
  const tbody = document.querySelector("#tbl-airports tbody");
  const codeInput = el("input", { type: "text", value: code, style: "text-transform:uppercase", maxlength: "3" });
  const labelInput = el("input", { type: "text", value: label, placeholder: "e.g. Nashville" });
  const delBtn = el("button", { class: "mp-btn-icon", onclick: () => { tr.remove(); onAirportsChanged(); } }, document.createTextNode("✕"));
  codeInput.addEventListener("input", onAirportsChanged);
  labelInput.addEventListener("input", refreshRouteOriginSelects);
  const tr = el("tr", {},
    el("td", {}, codeInput),
    el("td", {}, labelInput),
    el("td", {}, delBtn),
  );
  tbody.appendChild(tr);
  onAirportsChanged();
}

function getAirportRows() {
  return [...document.querySelectorAll("#tbl-airports tbody tr")].map(tr => {
    const inputs = tr.querySelectorAll("input");
    return { code: inputs[0].value.trim().toUpperCase(), label: inputs[1].value.trim() };
  }).filter(a => a.code);
}

function renderRoutes() {
  const tbody = document.querySelector("#tbl-routes tbody");
  tbody.innerHTML = "";
  (config.routes || []).forEach(r => addRouteRow(r.origin, r.destination, r.threshold_price));
}

function addRouteRow(origin = "", destination = "", threshold = 150) {
  const tbody = document.querySelector("#tbl-routes tbody");
  const originSel = airportSelect(origin);
  const destInput = el("input", { type: "text", value: destination, style: "text-transform:uppercase", maxlength: "3", placeholder: "IATA code" });
  const priceInput = el("input", { type: "number", value: threshold });
  const delBtn = el("button", { class: "mp-btn-icon", onclick: () => tr.remove() }, document.createTextNode("✕"));
  const tr = el("tr", {},
    el("td", {}, originSel),
    el("td", {}, destInput),
    el("td", {}, priceInput),
    el("td", {}, delBtn),
  );
  tbody.appendChild(tr);
}

function airportSelect(selected) {
  const sel = el("select", { style: "width:100%;background:#0b0d12;border:1px solid #262a33;color:#e8e9ec;border-radius:8px;padding:9px 11px;font-size:.9rem;font-family:inherit;" });
  getAirportRows().forEach(a => {
    const opt = el("option", { value: a.code, text: `${a.code} - ${a.label || a.code}` });
    if (a.code === selected) opt.setAttribute("selected", "selected");
    sel.appendChild(opt);
  });
  return sel;
}

function getRouteRows() {
  return [...document.querySelectorAll("#tbl-routes tbody tr")].map(tr => {
    const sel = tr.querySelector("select");
    const inputs = tr.querySelectorAll("input");
    return {
      origin: sel.value,
      destination: inputs[0].value.trim().toUpperCase(),
      threshold_price: Number(inputs[1].value) || null,
      currency: "USD",
      notes: "",
    };
  }).filter(r => r.origin && r.destination);
}

function renderAnywhereOriginChecks() {
  const wrap = document.getElementById("anywhere-origins");
  wrap.querySelectorAll("input").forEach(cb => {
    if (cb.checked) checkedOrigins.add(cb.value);
    else checkedOrigins.delete(cb.value);
  });
  wrap.innerHTML = "";
  getAirportRows().forEach(a => {
    const cb = el("input", { type: "checkbox", value: a.code });
    cb.checked = checkedOrigins.has(a.code);
    wrap.appendChild(el("label", {}, cb, document.createTextNode(` ${a.code} - ${a.label || a.code}`)));
  });
}

function renderAnywhere() {
  document.getElementById("max-price").value = (config.anywhere_scan || {}).max_price ?? 150;
  const chipBox = document.getElementById("dest-chips");
  const input = document.getElementById("dest-input");
  [...chipBox.querySelectorAll(".mp-chip")].forEach(c => c.remove());
  ((config.anywhere_scan || {}).destinations || []).forEach(code => addDestChip(code));

  input.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter" || ev.key === ",") {
      ev.preventDefault();
      const val = input.value.trim().toUpperCase().replace(/[^A-Z]/g, "");
      if (val) addDestChip(val);
      input.value = "";
    }
  });
}

function addDestChip(code) {
  const chipBox = document.getElementById("dest-chips");
  const input = document.getElementById("dest-input");
  if ([...chipBox.querySelectorAll(".mp-chip")].some(c => c.dataset.code === code)) return;
  const chip = el("span", { class: "mp-chip", "data-code": code },
    document.createTextNode(code),
    el("button", { onclick: () => chip.remove() }, document.createTextNode("✕")),
  );
  chipBox.insertBefore(chip, input);
}

function getDestChips() {
  return [...document.querySelectorAll("#dest-chips .mp-chip")].map(c => c.dataset.code);
}

function buildConfigFromForm() {
  const airports = {};
  getAirportRows().forEach(a => { airports[a.code] = { label: a.label || a.code }; });

  const origins = [...document.querySelectorAll("#anywhere-origins input:checked")].map(i => i.value);

  return {
    airports,
    routes: getRouteRows(),
    anywhere_scan: {
      origins,
      destinations: getDestChips(),
      max_price: Number(document.getElementById("max-price").value) || null,
      currency: "USD",
      notes: "Flags any destination from these airports that comes in at or under max_price, or that drops well below its own historical average. Leave \"destinations\" empty for true anywhere; list IATA codes to restrict to specific places. Managed from the dashboard's Manage panel.",
    },
    deal_rules: {
      drop_below_historical_avg_pct: Number(document.getElementById("pct-avg").value) || 20,
      drop_below_historical_min_pct: Number(document.getElementById("pct-min").value) || 10,
      realert_cooldown_hours: Number(document.getElementById("cooldown").value) || 24,
    },
  };
}

async function saveConfig() {
  const { repo } = getCreds();
  showStatus("status-save", "info", "Saving to GitHub...");
  try {
    const freshResp = await ghRequest(`/repos/${repo}/contents/config.json`);
    if (!freshResp.ok) throw new Error(`Couldn't re-check the file before saving (${freshResp.status}).`);
    const fresh = await freshResp.json();
    currentSha = fresh.sha;

    const newConfig = buildConfigFromForm();
    const body = {
      message: "Update settings via dashboard",
      content: b64EncodeUnicode(JSON.stringify(newConfig, null, 2) + "\n"),
      sha: currentSha,
    };
    const resp = await ghRequest(`/repos/${repo}/contents/config.json`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (resp.status === 409) throw new Error("Someone/something else updated the file at the same time. Reload the page and try again.");
    if (!resp.ok) throw new Error(`GitHub returned ${resp.status}: ${await resp.text()}`);
    const result = await resp.json();
    currentSha = result.content.sha;
    config = newConfig;
    showStatus("status-save", "ok", "Saved. Your new settings take effect on the next check.");
  } catch (err) {
    showStatus("status-save", "err", err.message);
  }
}

async function runNow() {
  const { repo } = getCreds();
  showStatus("status-save", "info", "Triggering a check now...");
  try {
    const resp = await ghRequest(`/repos/${repo}/actions/workflows/check-prices.yml/dispatches`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ref: "main" }),
    });
    if (resp.status === 404) throw new Error("Workflow not found, or this token doesn't have Actions permission - check the token's permissions.");
    if (!resp.ok && resp.status !== 204) throw new Error(`GitHub returned ${resp.status}: ${await resp.text()}`);
    showStatus("status-save", "ok", "Check triggered - it takes a minute or two. Refresh shortly to see results.");
  } catch (err) {
    showStatus("status-save", "err", err.message);
  }
}

document.getElementById("btn-connect").addEventListener("click", loadConfig);
document.getElementById("btn-forget").addEventListener("click", () => {
  localStorage.removeItem("ft_repo");
  localStorage.removeItem("ft_token");
  document.getElementById("token").value = "";
  showStatus("status-connect", "info", "Token forgotten on this device.");
});
document.getElementById("btn-add-airport").addEventListener("click", () => addAirportRow());
document.getElementById("btn-add-route").addEventListener("click", () => addRouteRow());
document.getElementById("btn-save").addEventListener("click", saveConfig);
document.getElementById("btn-run-now").addEventListener("click", runNow);

function ftToggleManage(forceOpen) {
  const panel = document.getElementById("manage-panel");
  const btn = document.getElementById("btn-toggle-manage");
  const opening = forceOpen !== undefined ? forceOpen : !panel.classList.contains("mp-open");
  panel.classList.toggle("mp-open", opening);
  btn.classList.toggle("active", opening);
  btn.textContent = opening ? "✕ Close" : "⚙️ Manage";
}

function ftOpenManage(focusId) {
  ftToggleManage(true);
  setTimeout(() => {
    const field = document.getElementById(focusId);
    if (field) { field.scrollIntoView({ behavior: "smooth", block: "center" }); field.focus(); }
  }, 380);
}

function ftApplyFilters() {
  const groups = document.querySelectorAll(".origin-group");
  const noMatches = document.getElementById("ft-no-matches");
  if (groups.length === 0) { if (noMatches) noMatches.style.display = "none"; return; }

  const q = (document.getElementById("ft-dest-search")?.value || "").trim().toUpperCase();
  const activeAirlines = [...document.querySelectorAll(".airline-pill.active")].map(p => p.dataset.airline);
  const noAirlineFilter = activeAirlines.length === 0;
  let anyVisible = false;

  groups.forEach(group => {
    let groupHasVisible = false;
    group.querySelectorAll(".card[data-dest]").forEach(card => {
      const dest = (card.dataset.dest || "").toUpperCase();
      const airline = card.dataset.airline || "";
      const matchesDest = !q || dest.includes(q);
      const matchesAirline = noAirlineFilter || activeAirlines.includes(airline);
      const show = matchesDest && matchesAirline;
      card.style.display = show ? "" : "none";
      if (show) groupHasVisible = true;
    });
    group.style.display = groupHasVisible ? "" : "none";
    if (groupHasVisible) anyVisible = true;
  });

  if (noMatches) noMatches.style.display = anyVisible ? "none" : "block";
}

function ftClearFilters() {
  const search = document.getElementById("ft-dest-search");
  if (search) search.value = "";
  document.querySelectorAll(".airline-pill.active").forEach(p => p.classList.remove("active"));
  ftApplyFilters();
}

window.addEventListener("DOMContentLoaded", () => {
  const { repo, token } = loadCredsFromStorage();
  if (repo && token) loadConfig();
});
</script>
"""


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
    distinct_airlines = set()
    for origin, dests in history.get("anywhere", {}).items():
        if dests:
            anywhere_groups.append(anywhere_group(cfg, origin, dests, max_price))
            for series in dests.values():
                if series.get("last_airline"):
                    distinct_airlines.add(series["last_airline"])
    filter_bar = filter_bar_html(sorted(distinct_airlines))

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
  nav a, .manage-toggle {{ text-decoration:none; color:var(--ink-2); background:var(--surface-2); border:1px solid var(--border); padding:10px 18px; border-radius:var(--radius-sm); font-size:.88rem; font-weight:600; transition:border-color .15s, color .15s; font-family:inherit; cursor:pointer; }}
  nav a:hover, .manage-toggle:hover {{ border-color:var(--accent); color:#fff; }}
  .manage-toggle.active {{ border-color:var(--accent); color:#fff; background:rgba(57,135,229,0.14); }}

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
  .chart-wrap {{ position:relative; height:54px; width:100%; flex:none; }}
  .chart-wrap canvas {{ position:absolute; inset:0; width:100% !important; height:100% !important; }}
  .card-foot {{ margin-top:auto; padding-top:var(--sp-1); }}
  .book-btn {{ display:inline-block; text-decoration:none; font-size:.82rem; font-weight:700; color:#06130c;
               background:linear-gradient(135deg,#1baf7a,#3987e5); padding:9px 15px; border-radius:var(--radius-sm); }}
  .book-btn:hover {{ filter:brightness(1.1); }}
  .book-btn.disabled {{ background:var(--surface-2); color:var(--muted); cursor:default; }}

  .more-note {{ margin-top:var(--sp-4); font-size:.82rem; color:var(--muted); }}

  .filter-bar {{ display:flex; flex-wrap:wrap; align-items:center; gap:var(--sp-3); margin-bottom:var(--sp-6); }}
  .filter-bar input {{ background:var(--surface); border:1px solid var(--border); color:var(--ink); border-radius:var(--radius-sm); padding:9px 13px; font-size:.85rem; font-family:inherit; min-width:220px; }}
  .filter-bar input:focus {{ outline:none; border-color:var(--accent); }}
  .pill-row {{ display:flex; flex-wrap:wrap; gap:var(--sp-2); }}
  .airline-pill {{ display:inline-flex; align-items:center; gap:6px; font-size:.78rem; font-family:inherit; color:var(--ink-2); background:var(--surface); border:1px solid var(--border); padding:6px 11px; border-radius:999px; cursor:pointer; transition:border-color .15s, background .15s; }}
  .airline-pill .dot {{ width:7px; height:7px; border-radius:50%; flex:none; }}
  .airline-pill:hover {{ border-color:rgba(255,255,255,0.25); }}
  .airline-pill.active {{ border-color:var(--accent); background:rgba(57,135,229,0.14); color:#fff; }}
  .filter-clear {{ background:none; border:none; color:var(--muted); font-size:.78rem; font-family:inherit; cursor:pointer; text-decoration:underline; padding:4px; }}
  .filter-clear:hover {{ color:var(--ink-2); }}

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
    <nav><button type="button" class="manage-toggle" id="btn-toggle-manage" onclick="ftToggleManage()">&#9881;&#65039; Manage</button></nav>
  </div>
  <div class="stat-row">{hero_stats(cfg, history)}</div>
</header>

{MANAGE_PANEL}

<main>
  <section>
    <h2>Tracked routes</h2>
    <div class="grid">
      {''.join(route_cards) if route_cards else '<div class="muted">No data yet - runs after the first scheduled check.</div>'}
    </div>
  </section>

  <section id="anywhere-section">
    <h2>Anywhere deals</h2>
    {filter_bar}
    {''.join(anywhere_groups) if anywhere_groups else '<div class="muted">No data yet, or no origins configured for the anywhere scan - set it up in Manage.</div>'}
    <div id="ft-no-matches" class="muted" style="display:none; padding:12px 0;">No destinations match those filters.</div>
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
