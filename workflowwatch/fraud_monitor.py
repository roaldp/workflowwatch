#!/usr/bin/env python3
"""
Fraud Monitor — detects when remote-desktop software and banking browser tabs
are active simultaneously. Shows a system notification and logs the incident.

Prerequisites:
  - ActivityWatch running on localhost:5600
  - ActivityWatch browser extension installed (for tab tracking)

Usage:
  pip install httpx plyer
  python fraud_monitor.py
"""

import json
import logging
import os
import signal
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

logger = logging.getLogger("fraud_monitor")

# ---------------------------------------------------------------------------
# Configuration (override via environment variables)
# ---------------------------------------------------------------------------
AW_URL = os.getenv("AW_URL", "http://localhost:5600")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "15"))  # seconds
ALERT_COOLDOWN = int(os.getenv("ALERT_COOLDOWN", "60"))  # seconds
LOG_FILE = os.getenv("FRAUD_LOG", str(Path(__file__).parent / "fraud_alerts.jsonl"))
LOOKBACK_MINUTES = int(os.getenv("LOOKBACK_MINUTES", "5"))

# ---------------------------------------------------------------------------
# Pattern lists
# ---------------------------------------------------------------------------
SCREEN_SHARING_APPS: list[str] = [
    "teamviewer",
    "anydesk",
    "rustdesk",
    "ultraviewer",
    "ammyy",
    "supremo",
    "connectwise",
    "logmein",
    "splashtop",
    "bomgar",
]

BANKING_URL_PATTERNS: list[str] = [
    "chase.com",
    "bankofamerica.com",
    "wellsfargo.com",
    "citi.com",
    "capitalone.com",
    "usbank.com",
    "pnc.com",
    "tdbank.com",
    "ally.com",
    "schwab.com",
    "fidelity.com",
    "paypal.com",
    "venmo.com",
    "zelle",
]

BANKING_TITLE_KEYWORDS: list[str] = [
    "online banking",
    "bank sign in",
    "bank login",
    "wire transfer",
    "send money",
    "zelle",
]

# ---------------------------------------------------------------------------
# ActivityWatch client (synchronous, minimal)
# ---------------------------------------------------------------------------

_http = httpx.Client(base_url=AW_URL, timeout=10.0)


def discover_buckets() -> dict[str, str | list[str]]:
    """Find relevant AW bucket IDs by type."""
    resp = _http.get("/api/0/buckets/")
    resp.raise_for_status()
    buckets = resp.json()

    window = None
    browser: list[str] = []
    for bid, meta in buckets.items():
        btype = meta.get("type", "")
        if btype == "currentwindow" and window is None:
            window = bid
        elif btype == "web.tab.current":
            browser.append(bid)

    if not window:
        logger.warning("No currentwindow bucket found — window detection disabled")
    if not browser:
        logger.warning("No browser buckets found — is the AW browser extension installed?")

    return {"window": window, "browser": browser}


def get_recent_events(bucket_id: str, minutes: int = LOOKBACK_MINUTES) -> list[dict]:
    """Fetch events from the last N minutes."""
    now = datetime.now(timezone.utc)
    start = now - timedelta(minutes=minutes)
    resp = _http.get(
        f"/api/0/buckets/{bucket_id}/events",
        params={"start": start.isoformat(), "end": now.isoformat(), "limit": -1},
    )
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Detection logic
# ---------------------------------------------------------------------------

def _parse_ts(ts: str) -> datetime:
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _event_interval(ev: dict) -> tuple[datetime, datetime]:
    start = _parse_ts(ev["timestamp"])
    end = start + timedelta(seconds=ev.get("duration", 0))
    return start, end


def check_fraud_pattern(
    window_events: list[dict],
    browser_events: list[dict],
) -> list[dict]:
    """Detect temporal overlaps between screen-sharing apps and banking tabs."""

    # Find screen-sharing intervals
    ss_intervals: list[tuple[datetime, datetime, str]] = []
    for ev in window_events:
        app = ev.get("data", {}).get("app", "").lower()
        for pattern in SCREEN_SHARING_APPS:
            if pattern in app:
                start, end = _event_interval(ev)
                ss_intervals.append((start, end, ev["data"]["app"]))
                break

    if not ss_intervals:
        return []

    # Find banking intervals
    bank_intervals: list[tuple[datetime, datetime, str]] = []
    for ev in browser_events:
        data = ev.get("data", {})
        url = data.get("url", "").lower()
        title = data.get("title", "").lower()
        indicator = None

        for pattern in BANKING_URL_PATTERNS:
            if pattern in url:
                indicator = pattern
                break
        if not indicator:
            for keyword in BANKING_TITLE_KEYWORDS:
                if keyword in title:
                    indicator = f'title:"{keyword}"'
                    break

        if indicator:
            start, end = _event_interval(ev)
            bank_intervals.append((start, end, indicator))

    if not bank_intervals:
        return []

    # Check for overlaps
    alerts: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for ss_start, ss_end, ss_app in ss_intervals:
        for bank_start, bank_end, bank_indicator in bank_intervals:
            overlap_start = max(ss_start, bank_start)
            overlap_end = min(ss_end, bank_end)
            if overlap_start < overlap_end:
                key = (ss_app.lower(), bank_indicator.lower())
                if key not in seen:
                    seen.add(key)
                    alerts.append({
                        "timestamp": overlap_start.isoformat(),
                        "overlap_seconds": (overlap_end - overlap_start).total_seconds(),
                        "screen_sharing_app": ss_app,
                        "banking_indicator": bank_indicator,
                    })

    alerts.sort(key=lambda a: a["timestamp"])
    return alerts


# ---------------------------------------------------------------------------
# Notification
# ---------------------------------------------------------------------------

def show_alert(alert: dict) -> None:
    """Show a system notification for a fraud alert."""
    app = alert["screen_sharing_app"]
    indicator = alert["banking_indicator"]
    try:
        from plyer import notification
        notification.notify(
            title="SECURITY ALERT",
            message=(
                f"Screen sharing ({app}) detected while banking site "
                f"({indicator}) is open.\n\n"
                "If someone asked you to install this software, "
                "hang up — it may be a scam."
            ),
            timeout=30,
            app_name="Fraud Monitor",
        )
        logger.info("Notification shown for %s + %s", app, indicator)
    except Exception:
        # Fallback: print to console if plyer fails
        logger.error(
            "ALERT: Screen sharing (%s) + banking (%s) detected! "
            "Could not show system notification — is plyer installed?",
            app, indicator,
        )


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def log_incident(alert: dict) -> None:
    """Append a JSON line to the incident log."""
    entry = {
        **alert,
        "logged_at": datetime.now(timezone.utc).isoformat(),
        "notified": True,
    }
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")
    logger.info("Incident logged to %s", LOG_FILE)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    logger.info("Fraud Monitor starting — polling %s every %ds", AW_URL, POLL_INTERVAL)

    # Discover buckets
    try:
        buckets = discover_buckets()
    except httpx.ConnectError:
        logger.error("Cannot connect to ActivityWatch at %s — is it running?", AW_URL)
        sys.exit(1)

    if not buckets["window"] and not buckets["browser"]:
        logger.error("No usable buckets found. Exiting.")
        sys.exit(1)

    logger.info(
        "Monitoring — window: %s, browser buckets: %d",
        buckets["window"],
        len(buckets["browser"]),
    )

    cooldown_until: datetime | None = None

    # Graceful shutdown
    running = True
    def _stop(sig, frame):
        nonlocal running
        logger.info("Shutting down...")
        running = False
    signal.signal(signal.SIGINT, _stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _stop)

    while running:
        try:
            # Fetch recent events
            window_events: list[dict] = []
            browser_events: list[dict] = []

            if buckets["window"]:
                window_events = get_recent_events(buckets["window"])

            for bid in buckets["browser"]:
                browser_events.extend(get_recent_events(bid))

            # Detect fraud patterns
            alerts = check_fraud_pattern(window_events, browser_events)

            now = datetime.now(timezone.utc)
            if alerts and (cooldown_until is None or now > cooldown_until):
                for alert in alerts:
                    show_alert(alert)
                    log_incident(alert)
                cooldown_until = now + timedelta(seconds=ALERT_COOLDOWN)
                logger.warning(
                    "FRAUD PATTERN DETECTED: %d alert(s) — cooldown for %ds",
                    len(alerts), ALERT_COOLDOWN,
                )
            elif not alerts:
                logger.debug("No fraud patterns detected")

        except httpx.ConnectError:
            logger.warning("Lost connection to ActivityWatch — will retry")
        except Exception:
            logger.exception("Unexpected error during poll")

        # Sleep in small increments so SIGINT is responsive
        for _ in range(POLL_INTERVAL):
            if not running:
                break
            time.sleep(1)

    logger.info("Fraud Monitor stopped")


if __name__ == "__main__":
    main()
