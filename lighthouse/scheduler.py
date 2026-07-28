"""Lighthouse in-process daily scheduler.

Runs Shadow Mode inside the already-deployed web service — no external Render cron, no separate
billing, no credential handling (the web service already has DATABASE_URL). Once per weekday after
the US close it logs the latest session's verdict. Safe by construction: run_shadow is idempotent
per (client,ticker,day), so multiple workers or a restart can't double-log; a persisted last-run
date avoids re-refreshing market data every check; and everything is wrapped so it can never affect
the app. Activates automatically on the next deploy via app.on_startup.
"""
from __future__ import annotations
import asyncio
import traceback
from datetime import datetime, timezone

CHECK_EVERY_SEC = 1800          # re-check every 30 minutes
RUN_AFTER_UTC_HOUR = 22         # ~ after the 4pm ET close (covers EST and EDT)
_STATE_KEY = "lighthouse_scheduler.json"
_STATE_CLIENT = "_lighthouse"   # fixed, tenant-independent state row
_started = False


def _last_run_date():
    try:
        from core import db
        return (db.load_json(_STATE_KEY, {}, client_id=_STATE_CLIENT) or {}).get("last_run_date")
    except Exception:
        return None


def _set_last_run_date(iso_date):
    try:
        from core import db
        db.save_json(_STATE_KEY, {"last_run_date": iso_date}, client_id=_STATE_CLIENT)
    except Exception:
        pass


def _should_run(now: datetime, last_iso: str | None) -> bool:
    """Weekday, at/after the post-close hour (UTC), and not already run today."""
    return now.weekday() < 5 and now.hour >= RUN_AFTER_UTC_HOUR and last_iso != now.date().isoformat()


def _run_once():
    from lighthouse import shadow
    got = shadow.run_shadow(days_back=1)
    print(f"[lighthouse-scheduler] shadow run: logged {len(got)} new verdict(s)")
    return got


async def _loop():
    print("[lighthouse-scheduler] started — daily post-close Shadow run (in-process, no external cron)")
    while True:
        try:
            now = datetime.now(timezone.utc)
            if _should_run(now, _last_run_date()):
                await asyncio.to_thread(_run_once)
                _set_last_run_date(now.date().isoformat())
        except Exception:
            traceback.print_exc()
        await asyncio.sleep(CHECK_EVERY_SEC)


def start():
    """Launch the daily loop once. Call from an async startup hook (a running event loop is required
    for asyncio.create_task). Idempotent."""
    global _started
    if _started:
        return
    asyncio.create_task(_loop())
    _started = True
