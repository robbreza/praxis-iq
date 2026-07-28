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

Remaining Phase 1: technician subset, continuous historical validation, then Shadow Mode.
See `docs/lighthouse/phased_build_plan.md`.

## The invariant
Every fact carries a `knowledge_ts` (when it became **knowable**, not its content date). All reads go
through `AsOf.visible()` / the `knowledge_ts <= as_of` SQL gate, so a backtest cannot leak the future
and historical replay reproduces exactly what was knowable at a chosen instant. Missing source ≠
nothing found.
