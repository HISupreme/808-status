# 808status

A public scoreboard of Hawaii state and county government website availability.
Pings ~30 .gov URLs every six hours and renders a public dashboard showing
what's broken, for how long, and 30-day uptime per page.

Sibling project of [808forms](https://github.com/USER/808forms).

## How it works

- **`urls.json`** — the list of URLs to monitor (hand-curated).
- **`check.py`** — the checker. Pings each URL, appends a row to `history.json`.
- **`history.json`** — append-only log of check results. Keyed by URL id so URL
  changes don't break the uptime graph.
- **`index.html`** — static dashboard. Reads the two JSON files client-side.
- **`.github/workflows/check.yml`** — runs `check.py` every 6 hours and commits
  the updated `history.json` back to the repo.

The whole thing is a static site with a cron job. No backend, no database, no
auth.

## Deploy

1. Fork this repo (or push it to a new repo of your own).
2. In the repo's **Settings → Pages**, set source to "Deploy from a branch",
   branch `main`, folder `/` (root). The dashboard publishes at
   `https://USERNAME.github.io/808status/` (or your custom domain).
3. In **Settings → Actions → General**, scroll to "Workflow permissions" and
   set it to **"Read and write permissions"** so the cron can commit back.
4. The workflow will start running on its 6-hour schedule. Trigger the first
   run manually from the **Actions** tab → "check" → "Run workflow".

## Local development

```bash
pip install -r requirements.txt
python check.py
python -m http.server 8000  # then open http://localhost:8000/
```

## Adding a URL

Edit `urls.json`. Each entry needs:

- `id` — stable slug. **Don't change this** even if the URL changes — the
  history is keyed off it.
- `url` — what to ping.
- `label` — human-readable name on the dashboard.
- `agency` — for grouping.
- `category` — `property`, `worker`, `housing`, `tax`, `health`,
  `hawaiian-home-lands`, or `civic`.
- `expect_status` — usually 200. Use other codes for pages that legitimately
  return non-200 (e.g., 401 for login-walled APIs).

## Why this exists

In April 2026, 808forms v1 shipped with 22 cards, of which the very first one
a user clicked 404'd because Honolulu RPAD had silently revised the form's
filename. The deeper failure mode: 60+ Hawaii .gov pages mishandle their own
forms in recurring, predictable ways. This is the meta-layer that audits them
in public.

The agencies will never audit themselves because each one wants to look fine.
An external audit, published, with no permission requested, is the only thing
that produces accountability.
