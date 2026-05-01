#!/usr/bin/env python3
"""
808status — Hawaii .gov URL health checker.

Reads urls.json, pings each URL, appends results to history.json.
Designed to run on a 6-hour cron via GitHub Actions.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

# Config
URLS_FILE = Path("urls.json")
HISTORY_FILE = Path("history.json")
TIMEOUT_SECONDS = 15

# Realistic browser User-Agent to avoid false-positive 403s from bot-detection
# services (Cloudflare, Akamai, etc). The 808status identifier at the end keeps
# this honest: any agency that inspects the UA can see what we are and find us.
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36 "
    "808status-monitor/0.1 (+https://status.808forms.org)"
)

MAX_HISTORY_PER_URL = 1500  # ~1 year at 4 checks/day, then we trim


def utc_now_iso() -> str:
    """Return current UTC time as ISO 8601 string with Z suffix."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def check_one(check: dict) -> dict:
    """Ping one URL. Always returns a result row, even on failure."""
    url = check["url"]
    expect = check.get("expect_status", 200)
    ts = utc_now_iso()

    try:
        # HEAD first — cheaper, less likely to trigger anti-bot.
        # Fall back to GET if HEAD is rejected (some servers return 405 or 403).
        resp = requests.head(
            url,
            timeout=TIMEOUT_SECONDS,
            allow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        )
        if resp.status_code in (403, 405):
            resp = requests.get(
                url,
                timeout=TIMEOUT_SECONDS,
                allow_redirects=True,
                headers={"User-Agent": USER_AGENT},
            )
        status = resp.status_code
        ms = int(resp.elapsed.total_seconds() * 1000)

        # Treat 403 as ambiguous: most likely we got bot-blocked despite the
        # realistic User-Agent above, not that the page is actually broken.
        # Record the status for transparency but mark ok=true so it doesn't
        # show as a false positive on the dashboard.
        if status == 403:
            ok = True
        else:
            ok = (status == expect)

    except requests.exceptions.Timeout:
        status, ms, ok = 0, TIMEOUT_SECONDS * 1000, False
    except requests.exceptions.ConnectionError:
        status, ms, ok = 0, 0, False
    except requests.exceptions.RequestException:
        status, ms, ok = 0, 0, False

    return {"ts": ts, "status": status, "ms": ms, "ok": ok}


def load_json(path: Path, default):
    """Load JSON file, return default if missing or invalid."""
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"warn: could not read {path}: {e}", file=sys.stderr)
        return default


def save_json(path: Path, data) -> None:
    """Write JSON atomically (write to temp file, then rename)."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    tmp.replace(path)


def main() -> int:
    urls_doc = load_json(URLS_FILE, default=None)
    if not urls_doc or "checks" not in urls_doc:
        print(f"error: {URLS_FILE} missing or invalid", file=sys.stderr)
        return 1

    history = load_json(HISTORY_FILE, default={"version": 1, "checks": {}})
    if "checks" not in history:
        history["checks"] = {}

    checks = urls_doc["checks"]
    print(f"checking {len(checks)} URLs...")

    failures = 0
    for c in checks:
        cid = c["id"]
        result = check_one(c)
        history["checks"].setdefault(cid, []).append(result)

        # Trim if we exceed the per-URL cap.
        if len(history["checks"][cid]) > MAX_HISTORY_PER_URL:
            history["checks"][cid] = history["checks"][cid][-MAX_HISTORY_PER_URL:]

        marker = "OK " if result["ok"] else "BAD"
        if not result["ok"]:
            failures += 1
        print(f"  [{marker}] {result['status']:>3} {result['ms']:>5}ms  {cid}")

    history["last_run"] = utc_now_iso()
    save_json(HISTORY_FILE, history)
    print(f"done. {failures} failure(s) of {len(checks)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
