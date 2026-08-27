# IRconnect — Production Deployment (Render + Neon)

Logical multi-tenant: **one** always-on app instance serves every customer, with all data
isolated by `client_id`. This runbook stands up that instance on Render with a Neon Postgres
backend. Target scale: ~10 tenants × ~3 users — comfortably one instance.

> **Why always-on (not serverless):** NiceGUI holds live websocket sessions, an in-process
> cache (`_MEM_CACHE`), and background jobs (market refresh, digest scheduler, peer-watch).
> These assume one long-lived process. Do not run it on a plan that spins down on idle.

---

## 0. Region pairing (do this decision first)

**The dominant rule: Neon and Render must sit in the SAME cloud region.** A page render makes many
sequential DB round-trips; when the app server and Neon are co-located they're ~1–3 ms each, and the
whole prefetch/perf effort holds. Split them across regions and you put ~50–80 ms back on *every*
round-trip — undoing that work. Co-location matters more than being physically near your users,
because the browser↔server link is a websocket (few round-trips per click) while the server↔DB link
is dozens.

**Recommended pair — US-East (finance, East-Coast weighted):**

| Piece | Pick | Why |
|---|---|---|
| Render | **Virginia** | Render Virginia is AWS `us-east-1` |
| Neon | **AWS `us-east-1` (N. Virginia)** | Same AWS region as Render Virginia → lowest possible DB latency |

This fits your user base (US micro-cap issuers + a buy-side that's overwhelmingly NY/Boston/East-Coast):
~10–30 ms to East-Coast users, and an acceptable ~60–70 ms to any West-Coast fund — and the DB
co-location is what preserves the render speed regardless of where a given user sits.

**Discipline:**
- **Pick the two as a pair, both on AWS.** Don't mix (e.g. Neon *Azure* East US with Render AWS
  Virginia is cross-cloud and adds latency). Neon → AWS `us-east-1`; Render → Virginia.
- **Don't split regions** to chase a few West-Coast users. One co-located US-East region is the right
  answer until you have a large, geographically-clustered cohort abroad.
- **Fallback pair** (capacity/preference): Render **Ohio** ↔ Neon **AWS `us-east-2` (Ohio)** — also
  same-region; use it only if you deliberately choose Ohio for both.
- Set `region: virginia` in `render.yaml` (already the default) so it matches the Neon pick above.

## 1. Neon (database)

1. Create a Neon project **in AWS `us-east-1` (N. Virginia)** — the pair for Render Virginia (see §0).
   Co-location turns per-page DB latency from ~80 ms/round-trip into single digits.
2. Copy the **pooled** connection string (Connection Details → *Pooled connection*; host looks like
   `…-pooler.…neon.tech`). The app opens many short connections, so the pooler endpoint is correct.
   It must include `?sslmode=require`.
3. On a **paid** Neon plan, disable "scale to zero" (or set a long suspend). Neon's auto-suspend is
   the ~4.6 s *first-page* cold-start you'd otherwise see after any idle period.
4. **No manual migration needed** — the app creates its schema on first boot (client_data, documents,
   lh_* tables, etc.). Just point `DATABASE_URL` at the empty database.

## 2. Secrets to prepare

| Secret | How to get it | Required? |
|---|---|---|
| `DATABASE_URL` | Neon pooled string (step 1) | **Yes** — without it the app silently falls back to on-disk SQLite, which Render **wipes on every deploy** (data loss). |
| `ANTHROPIC_API_KEY` | console.anthropic.com | For AI features (script gen/refine). App boots without it but AI degrades to templates. |
| `IRCONNECT_STORAGE_SECRET` | Render generates it (`generateValue: true`) | **Yes** — handled by the blueprint. |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | you choose | **Yes** — seeds the first admin on boot. |
| `DEFAULT_USER_PASSWORD` | you choose | Initial password for provisioned client users. |
| `LIGHTHOUSE_APP_URL` | your prod URL | Used in digest/push deep links. |
| `VAPID_*` | generate a VAPID keypair (pywebpush) | Optional — phone alerts; app boots without them. |
| `ZOHO_SMTP_*` / `MAIL_IMAP_*` | your mail provider | Optional — outbound digests / inbound inbox polling. |

## 3. Render (app)

1. **New → Blueprint**, point at this repo. It reads `render.yaml` (web service, `standard` plan,
   `python app_nicegui.py`, health check `/version`, auto-deploy from `main`).
2. Set `region` in `render.yaml` to match your Neon region before applying.
3. In the service's **Environment** tab, fill every `sync: false` secret from the table above.
4. Deploy. First build runs `pip install -r requirements.txt`; first boot creates the schema and
   seeds the admin. `runtime.txt` pins Python 3.12.

## 4. Critical DON'Ts (each is a real incident waiting to happen)

- **Never set `DEV_AUTOLOGIN` or `DEV_TENANT` in production.** `DEV_AUTOLOGIN` bypasses the login
  screen entirely — anyone hitting the URL gets a signed-in session. Their *absence* is correct.
- **Never leave `DATABASE_URL` unset.** The SQLite fallback lives on Render's ephemeral disk and is
  erased on every deploy/restart.
- **Never use a spin-down plan** (Render free). It kills the background jobs and cold-starts.

## 5. SEC / EDGAR fair-access

The crawler already **paces globally to ≤10 req/s** (SEC's fair-access limit) and sends a
`User-Agent` of `"{client name} {contact email}"`. SEC requires a **real, monitored contact** —
make sure each tenant's IR contact email is real (it's what SEC sees). SEC data is free; the pulls
are background jobs that cache into Neon, so they never sit on a user's render path.

## 6. First-boot checklist

- [ ] `GET /version` returns 200 (health check green).
- [ ] Log in with `ADMIN_EMAIL` / `ADMIN_PASSWORD`.
- [ ] A tenant page (Today) renders; `Lighthouse` warms after first visit.
- [ ] Logs show no `DATABASE_URL` / storage-secret fallback warnings.
- [ ] (If email configured) a test digest sends; (if push) VAPID key endpoint responds.

## 7. Custom domain

Point `app.praxispointir.com` (CNAME) at the Render service, add it in Render → Custom Domains
(auto-TLS), and set `LIGHTHOUSE_APP_URL` to `https://app.praxispointir.com`.

## 8. Cost (small production, ~10 tenants)

| Component | Est. /mo |
|---|---|
| Render web service (Standard, 2 GB, always-on) | ~$25 |
| Neon Postgres (paid; no scale-to-zero) | ~$19 |
| Anthropic API (usage) | ~$20–80 |
| Marketing site (static) | ~$0 |
| **Total** | **~$65–125** |

SEC pulls barely register — free data, KB-scale JSON caches, background compute on the instance
you already pay for.

## 9. Scaling ceiling (know it, don't pre-solve it)

This is a **single-process** design: the in-process cache and background jobs assume one instance.
That's ideal to ~dozens of tenants. Going to *many* instances (horizontal scale) later requires a
shared cache + a single-owner for the background jobs (e.g. move the scheduler to one worker, or a
Render Cron/background worker) — a deliberate re-architecture, not a config flip. Not needed now.
