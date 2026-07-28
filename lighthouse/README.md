# Lighthouse (module)

IR market-intelligence engine answering **"why is the stock moving today?"** — built inside the
Praxis platform to reuse its SEC parsing, peer construction, 13F/CRM data, market_data, and
multi-tenant `client_id` isolation. Governing specs and the phased plan live in `docs/lighthouse/`.

## Status — Phase 0 (foundations & the no-look-ahead spine)
- [x] `replay.py` — `AsOf` point-in-time horizon (the one non-negotiable invariant) + guards
- [x] `schema.sql` — security master, OHLCV, peers, events, feature store, model runs, verdicts
      (draft→revised→settled lifecycle), evidence lineage — all `knowledge_ts`-stamped, `client_id`-scoped
- [x] `config/usio.py` — first client config (ticker-agnostic, configuration-driven)
- [x] `tests/test_lighthouse_replay.py` — CI gate on no-look-ahead
- [x] historical OHLCV wired into `lh_ohlcv` via yfinance (`data.py`) — 751d x 10 tickers
- [x] business peer set into `lh_peer` (`data.build_peers`); dynamic mktcap/liquidity peers next
- [x] point-in-time returns frame (`data.returns_frame`); full feature store next
- [x] **first expected/actual/residual** — rolling market+peer OLS (`attribution.py`), 624 USIO days

## Next (Phase 1 — V0.1 Historical Intelligence Engine)
- [x] **Event Intelligence overlay** (`events.py`) — SEC submissions -> lh_event (knowledge_ts =
  acceptanceDateTime), Spec-12 timing test (candidate cause / rolls-to-next-session / prior-window
  diffusion / checked-but-not-found). Matches USIO earnings (10-Q) reactions incl. the T-1 lag.

- [x] **Evidence Fusion v0 + CEO one-pager** (`ceo.py`) — fuses attribution + events into a
  conclusion-first CEO note: separates abnormality vs explanation confidence, drivers (primary/
  contributing/diffusing/unexplained), found vs checked-but-not-found, deep-linked evidence;
  persists to lh_verdict as draft (Spec 12.4 lifecycle).

- [x] **Technician's Model** (`technician.py`) — trend/support-resistance/RVOL/ATR/rel-strength/gap,
  every signal tagged amplifier|contributor (never trigger); folded into the CEO note as the "how".

- [x] **Continuous historical validation** (`validation.py`) — 624 days: alert burden ~32/yr,
  event lens fires 2.1x post-filing, 52% of big moves SEC-explained (rest -> Phase 3 flow/news lenses).
- [x] **App view** (`page_modules_nicegui/lighthouse_page.py`) — CEO one-pager cards in the NiceGUI
  shell (nav + RBAC wired; ~2.5s render, shared DB conn).

- [x] **Shadow Mode ENTERED** (`shadow.py`) — daily live run logs the latest session's verdict to
  lh_verdict for IR review, NO automated executive alerts (Spec Stage 3). Track record seeded; a
  status banner shows on the Lighthouse page. Runs automatically via the in-process
  scheduler (`scheduler.py`, wired into app.on_startup) — daily post-close, no external cron needed;
  `python -m lighthouse.shadow` also works as a standalone cron if you ever want the isolation.

- [x] **Weekly Digest** (`weekly.py`) — rolls the daily attribution up to the week; headline metric
  is CUMULATIVE UNEXPLAINED DRIFT + a weekly rarity percentile (a week can be 90th-pctile abnormal on
  the sum of small daily moves with no dramatic day). Surfaces sustained multi-week drift the daily
  view fragments. Weekly card shows atop the Lighthouse page.

- [x] **Holder / forced-seller lens** (`holders.py`) — the Praxis moat: cross-references the move
  against the issuer's own 13F holder base (reused from the platform) to name reducers/exiters,
  splitting fundamental vs mechanical (quant/passive/MM); surfaced in the weekly digest on
  unexplained-drift weeks with the 13F-lag caveat. A standalone tool structurally can't do this.

**Phase 1 V0.1 complete + in Shadow Mode (all four lenses + holder moat + weekly digest).** Gate 1 next: run the record, get a CEO to say "I'd pay";
then Phase 3 flow / holder-forced-seller (13F/CRM moat) + private-company intel, by customer pull.
See `docs/lighthouse/phased_build_plan.md`.

## The invariant
Every fact carries a `knowledge_ts` (when it became **knowable**, not its content date). All reads go
through `AsOf.visible()` / the `knowledge_ts <= as_of` SQL gate, so a backtest cannot leak the future
and historical replay reproduces exactly what was knowable at a chosen instant. Missing source ≠
nothing found.
