"""scripts/refresh_holder_moves.py — standalone quarterly holder-move briefing refresh.

Run by a Windows Scheduled Task so the client board briefings stay current even while the app is
DOWN (the app's own _kick_off_holder_moves_refresh only runs while it's up). Mirrors that hook:
re-prepares each client's holder-move briefing ONLY when a NEW 13F quarter has posted (a cheap
staleness check; the ~90s SEC pull runs just for stale clients, so this is safe to run weekly and
does real work ~4x/year). The illustrative demo tenant is skipped. Appends to
logs/holder_moves_refresh.log. Self-contained: chdir to the project root so python-dotenv finds
.env regardless of the scheduler's working directory.
"""
import os
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)                      # so core.security.load_environment() finds .env from any cwd
sys.path.insert(0, ROOT)

from core import security           # noqa: E402
security.load_environment()

from config.client_config import CLIENT_REGISTRY, reload_registry   # noqa: E402
from core import prospect_hook                                      # noqa: E402


def main():
    reload_registry()               # pick up DB-defined tenants (saro/ceva/...), same as app startup
    clients = [(cid, rec.get("ticker"), rec.get("name"))
               for cid, rec in CLIENT_REGISTRY.items() if rec.get("ticker")]
    results = prospect_hook.refresh_client_briefings(clients)

    stamp = datetime.now().isoformat(timespec="seconds")
    os.makedirs(os.path.join(ROOT, "logs"), exist_ok=True)
    with open(os.path.join(ROOT, "logs", "holder_moves_refresh.log"), "a", encoding="utf-8") as f:
        for r in results:
            f.write(f"{stamp}  {r.get('client')}/{r.get('ticker')}  {r.get('status')}"
                    + (f"  ERROR: {r['error']}" if r.get("error") else "") + "\n")
    did = sum(1 for r in results if r.get("status") == "refreshed")
    print(f"{stamp}  holder-move refresh: {did} refreshed, {len(results) - did} current/skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
