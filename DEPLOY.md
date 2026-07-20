# Deploying IRconnect (reachable instance)

The app is a NiceGUI (uvicorn + websockets) server. To let an external reviewer like Paul reach
it, it needs a host that runs a long-lived Python process **with websocket support** and terminates
HTTPS for you. Same Neon database, real current data.

Code is already deployment-ready: `app_nicegui.py` binds `0.0.0.0` and reads `$PORT` from the
environment (defaults to 8502 locally).

## Recommended host: Render (simplest for NiceGUI)

Render supports websockets, gives you HTTPS + a URL out of the box, and has a low-cost tier.
Railway, Fly.io, or a small VPS also work — the steps below map cleanly to any of them.

1. **Repo** — already on GitHub: `robbreza/praxis-iq` (main is current).
2. **New → Web Service**, connect the repo, branch `main`.
3. **Runtime:** Python 3.
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `python app_nicegui.py`
   - Render injects `$PORT`; the app binds it automatically.
   - **Python version:** pinned to **3.12** via the committed `.python-version`. The code needs
     **≥3.11** (`datetime.fromisoformat` must parse space-separated timestamps with a UTC offset —
     that's the market-cache timezone fix). If Render ignores the file, also set a
     `PYTHON_VERSION=3.12` environment variable.
   - *Build weight:* `requirements.txt` still includes **streamlit** (for the legacy `app.py`
     during the NiceGUI migration). It installs from wheels so it won't fail, just adds build time
     and image size. Once `app.py` is retired, dropping it slims the deploy.
4. **Instance:** a single instance (do **not** scale to multiple — the per-process caches assume
   one process; the signed session cookie itself is fine, but keep it to one instance).
5. **Environment variables** (Settings → Environment):

   | Var | Value |
   |---|---|
   | `DATABASE_URL` | the Neon connection string (same one in local `.env`) |
   | `IRCONNECT_STORAGE_SECRET` | a strong random value — **required** (signs the session cookie) |
   | `ANTHROPIC_API_KEY` | the Anthropic key |
   | `DEFAULT_USER_PASSWORD` | optional; defaults to `IRconnect01` |

   `ADMIN_EMAIL`/`ADMIN_PASSWORD` are **not** needed — the `PPADMIN@praxispoint.com` staff admin
   already exists in Neon. `PORT` is set by Render.
6. **Deploy.** First boot overlays the client registry from Neon and seeds logins (idempotent).
7. Render gives you `https://<name>.onrender.com` — that's the URL for Paul.

> Note: on a free tier the service sleeps when idle, so the first hit after a nap is slow (cold
> start); Neon's free tier auto-suspends similarly. Fine for a review; move to a paid tier for a
> real client-facing instance.

## Pre-deploy gate (run locally, must be green before you push)

- [ ] **`python tests/smoke_render.py`** → `0 render failures · 0 demo leaks`. Renders every page
      for every tenant into a headless client and fails on any exception OR any fabricated demo
      string reaching a client surface. An HTTP 200 on `/` does NOT prove a page renders (NiceGUI
      builds pages on websocket navigation, not the GET), and this is what catches the
      "server did not load" crashes and demo-data leaks before a client sees them. Runs in ~1 min.

## Pre-exposure security checklist (before sending Paul the URL)

- [x] **HTTPS only** — Render terminates TLS; only share the `https://` URL.
- [ ] **`IRCONNECT_STORAGE_SECRET` set on the host** to a strong value (not the dev default).
- [x] **Tenant isolation** — Paul is a `client_user` pinned to `usio`; `allowed_clients` is
      server-derived and clamps any forged cookie. (Verified.)
- [x] **Read-only** — `client_user` writes are refused at the data layer. (Verified.)
- [x] **Operator surfaces gated** — `/console`, `/console/calendar`, `/admin/users` bounce
      non-staff; Paul cannot reach them. (Verified.)
- [x] **Forced rotation** — Paul must change `IRconnect01` on first login.
- [x] **`reload=False`** (production) and Neon over TLS.
- [ ] Confirm no other client's data is expected in USIO's views (Paul only sees USIO).

## Paul's login

- **URL:** the Render HTTPS URL
- **Email:** `paul.manley@usio.com`
- **Temp password:** `IRconnect01` (he'll be forced to set a new ≥10-char password on first login)
- He lands in USIO's workspace, read-only; **Investor Targeting → Target Database** is the current
  data he's reviewing. Convey the temp password to him out of band (not in the same email as the URL).
