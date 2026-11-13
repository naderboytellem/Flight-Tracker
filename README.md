# Flight Price Tracker

A personal flight-deal watcher, in the spirit of Going.com / NashvilleCheapFlights:
it checks your routes on a schedule, remembers what prices normally look like,
and pings your phone, computer, and email the moment something is a real deal
(at/under a price you set, a new historical low, or a big drop vs. the recent
average) — for both specific routes (Nashville ↔ LA) and "anywhere" scans from
your home airports.

It runs for free on GitHub Actions (the schedule), GitHub Pages (the
dashboard) and your own accounts for data + alerts (Amadeus, ntfy.sh, email).
Nothing needs to stay running on your computer.

## What's inside

- `config.json` — your airports, routes, price thresholds, and deal rules.
- `src/travelpayouts_client.py` — talks to the Travelpayouts (Aviasales) flight-price API.
- `src/storage.py` — keeps price history in `data/price_history.json` (committed to the repo each run, so it's just a readable file, not a database).
- `src/alerts.py` — sends email (SMTP) and push (ntfy.sh) alerts.
- `src/check_prices.py` — the main script: checks prices, decides what's a deal, fires alerts.
- `src/dashboard.py` — rebuilds `docs/index.html`, a dark little dashboard of current prices, history, and recent alerts.
- `.github/workflows/check-prices.yml` — runs the check every 6 hours automatically, and commits the updated data + dashboard.

## One-time setup (about 15–20 minutes total)

### 1. Get a free Travelpayouts API token (flight price data)

(Amadeus used to have a free self-service API for this, which is what I
originally pointed you at — but Amadeus shut that program down in July
2026 and stopped issuing new keys, so this uses Travelpayouts instead,
the free data feed behind Aviasales.)

1. Go to https://www.travelpayouts.com and sign up (free, no credit card — it's built for travel affiliates, so it'll ask for "a public channel" like a website or social account, but you don't need to actually use it for anything).
2. Once in, find your API token under your account's API/Tools section.
3. That's `TRAVELPAYOUTS_TOKEN`.

Note: this data comes from a 7-day cache of real traveler searches, not
a live booking-engine quote — same caveat as before: treat every alert
as "go check the real price," not a guaranteed fare. The exact response
shape wasn't fully pinned down from docs alone, so after your first real
scheduled run, check the Action's log — if a route or anywhere-scan comes
back empty when it shouldn't, tell me and I'll adjust the parsing in
`travelpayouts_client.py`.

### 2. Set up push notifications (ntfy.sh — free, no account)

1. Pick a topic name only you'd guess, e.g. `nader-dwp-flights-7q2m9k` (topic names are the only "password," so don't make it short or obvious).
2. On your phone: install the **ntfy** app (iOS App Store / Google Play), open it, tap "+", and subscribe to that exact topic name.
3. On your computer: open `https://ntfy.sh/<your-topic-name>` in a browser tab, or install the ntfy desktop app, and subscribe the same way. Leave it logged in — notifications land there automatically.
4. That topic name is your `NTFY_TOPIC` secret.

### 3. Set up email alerts

Easiest with Gmail:
1. Turn on 2-Step Verification on your Google account (if not already on).
2. Go to https://myaccount.google.com/apppasswords and create an app password.
3. Your secrets: `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`, `SMTP_USER` = your Gmail address, `SMTP_PASS` = the app password, `ALERT_EMAIL_TO` = where you want alerts sent (can be the same address).

Using Outlook/Office 365 instead? Same idea: `SMTP_HOST=smtp.office365.com`, `SMTP_PORT=587`, an app password from account security settings.

### 4. Put this code in a GitHub repo

If you don't already have a GitHub account, make a free one at github.com.

**Option A — I push it for you:** give me a GitHub [personal access token](https://github.com/settings/tokens) with `repo` and `workflow` scope, and tell me the repo name you want, and I'll create the repo, push this code, and set the secrets for you (paste the Travelpayouts/ntfy/email values too, or just the token and I'll ask for those next).

**Option B — you do it yourself:**
1. Create a new repo on GitHub (private is fine).
2. Upload all these files to it (drag-and-drop on github.com works, or `git init && git add . && git commit -m "init" && git push`).
3. Go to **Settings → Secrets and variables → Actions → New repository secret** and add each of: `TRAVELPAYOUTS_TOKEN`, `NTFY_TOPIC`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `ALERT_EMAIL_TO`.
4. Go to **Settings → Pages**, set Source = "Deploy from a branch", branch = `main`, folder = `/docs`. Save — GitHub gives you a URL like `https://<you>.github.io/<repo>/`. That's your dashboard, bookmark it.
5. Go to the **Actions** tab, open "Check flight prices," and click **Run workflow** once to test it manually instead of waiting 6 hours.

## Changing what it tracks

Edit `config.json`:
- `routes` — add/remove specific origin→destination pairs and a `threshold_price` for each.
- `anywhere_scan.origins` — which airports get scanned for "anywhere" deals, and `max_price` as the anywhere cutoff.
- `deal_rules` — how big a drop counts as a deal, and how many hours before re-alerting on the same route.

Just ask me to edit it and I'll make the change and hand you the updated file (or push it, if I have your repo access).

## Good to know

- Travelpayouts' limits are per-second rate limits rather than a hard monthly cap, so checking a couple of routes and two "anywhere" origins every 6 hours is comfortably fine.
- Email and push are both optional independently — if you only fill in the ntfy secret, you'll just get push; same for email-only.
- `data/price_history.json` is plain text and gets committed to your repo every run, so you always have a plain-English record of what it saw and when.
