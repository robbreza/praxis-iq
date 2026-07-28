-- Lighthouse Phase 0 — database schema (Postgres).
-- Every time series and event carries knowledge_ts (when the fact became KNOWABLE) so historical
-- replay is point-in-time. Everything is client_id-scoped for multi-tenant isolation (Spec: Data Ops).

-- ── Security master ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS lh_security (
  client_id      text NOT NULL,
  ticker         text NOT NULL,
  name           text,
  figi           text,
  cik            text,
  sector         text,
  sub_industry   text,
  active         boolean DEFAULT true,
  meta           jsonb,
  PRIMARY KEY (client_id, ticker)
);

-- ── Adjusted OHLCV (issuer, benchmarks, peers all live here, distinguished by role) ──
CREATE TABLE IF NOT EXISTS lh_ohlcv (
  ticker         text NOT NULL,
  d              date NOT NULL,        -- trading date the bar describes
  open           double precision,
  high           double precision,
  low            double precision,
  close          double precision,
  adj_close      double precision,     -- corporate-action adjusted
  volume         bigint,
  knowledge_ts   timestamptz NOT NULL, -- when this bar became knowable (>= session close)
  source         text,
  PRIMARY KEY (ticker, d)
);
CREATE INDEX IF NOT EXISTS lh_ohlcv_know ON lh_ohlcv (ticker, knowledge_ts);

-- ── Peer sets (business / dynamic market-cap / liquidity / statistical), versioned ──
CREATE TABLE IF NOT EXISTS lh_peer (
  client_id      text NOT NULL,
  ticker         text NOT NULL,        -- the issuer
  peer_ticker    text NOT NULL,
  peer_kind      text NOT NULL,        -- business | mktcap | liquidity | statistical
  weight         double precision,
  effective_from date NOT NULL,        -- peer membership is time-varying; keep history
  effective_to   date,
  knowledge_ts   timestamptz NOT NULL,
  PRIMARY KEY (client_id, ticker, peer_ticker, peer_kind, effective_from)
);

-- ── Events (SEC filings, announcements, peer/macro), timing-tested per Spec 4 + Spec 12 ──
CREATE TABLE IF NOT EXISTS lh_event (
  event_id       bigserial PRIMARY KEY,
  client_id      text NOT NULL,
  ticker         text,                 -- null for macro/market-wide
  kind           text NOT NULL,        -- sec_filing | announcement | earnings | insider | peer | macro | private_competitor
  headline       text,
  published_at   timestamptz NOT NULL, -- == knowledge_ts: when it became public/knowable
  effective_at   timestamptz,          -- when the fact takes effect, if different
  materiality    text,                 -- confirmed | supporting | soft | speculation
  direction      text,                 -- pos | neg | neutral | unknown
  info_state     text DEFAULT 'latent',-- Spec 12: latent | diffusing | priced | stale
  url            text,
  payload        jsonb,
  KNOWLEDGE_TS   timestamptz GENERATED ALWAYS AS (published_at) STORED
);
CREATE INDEX IF NOT EXISTS lh_event_know ON lh_event (client_id, ticker, published_at);

-- ── Feature store (per ticker/day, point-in-time) ────────────────────────────
CREATE TABLE IF NOT EXISTS lh_feature (
  ticker         text NOT NULL,
  d              date NOT NULL,
  name           text NOT NULL,        -- e.g. ret_1d, rvol_21, atr_14, mktcap, beta_63
  value          double precision,
  knowledge_ts   timestamptz NOT NULL,
  PRIMARY KEY (ticker, d, name)
);

-- ── Model runs (champion/challenger; expected vs actual vs residual) ─────────
CREATE TABLE IF NOT EXISTS lh_model_run (
  run_id         bigserial PRIMARY KEY,
  client_id      text NOT NULL,
  ticker         text NOT NULL,
  d              date NOT NULL,
  model          text NOT NULL,        -- naive | ols_static | ols_roll_63 | ols_roll_126 | ols_roll_252 | ...
  expected_ret   double precision,
  expected_lo    double precision,
  expected_hi    double precision,
  actual_ret     double precision,
  residual       double precision,
  residual_pctile double precision,
  as_of          timestamptz NOT NULL, -- the replay horizon this run was computed under
  model_version  text,
  data_version   text
);
CREATE INDEX IF NOT EXISTS lh_model_run_key ON lh_model_run (client_id, ticker, d, model);

-- ── Verdicts (Spec 12.4 lifecycle: draft -> revised -> settled) ──────────────
CREATE TABLE IF NOT EXISTS lh_verdict (
  verdict_id     bigserial PRIMARY KEY,
  client_id      text NOT NULL,
  ticker         text NOT NULL,
  d              date NOT NULL,
  as_of          timestamptz NOT NULL,
  lifecycle      text NOT NULL DEFAULT 'draft',  -- draft | revised | settled
  supersedes     bigint REFERENCES lh_verdict(verdict_id),
  abnormality_conf double precision,
  explanation_conf double precision,
  summary        text,                 -- the CEO one-liner
  drivers        jsonb,                -- [{class: primary|contributing|amplifier|coincident|diffusing|anticipatory|rejected, ...}]
  found          jsonb,                -- what was found
  not_found      jsonb,                -- what was checked but not found (Spec 4: missing != nothing)
  created_at     timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS lh_verdict_key ON lh_verdict (client_id, ticker, d, as_of);

-- ── Evidence (lineage; prevents double-counting per Spec: Evidence Fusion) ───
CREATE TABLE IF NOT EXISTS lh_evidence (
  evidence_id    bigserial PRIMARY KEY,
  verdict_id     bigint REFERENCES lh_verdict(verdict_id),
  chain_id       text,                 -- one causal chain = one contribution (dedupe)
  kind           text,                 -- event | residual | technical | flow | sell_side | soft
  ref_table      text,
  ref_id         text,
  knowledge_ts   timestamptz NOT NULL,
  deep_link      text,                 -- one-click evidence (Spec: never make the CEO search)
  detail         jsonb
);
