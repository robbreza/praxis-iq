"""Firm-type refinement for the Wiza equity-research cohort. The ingest ran firm_type_for() on the
NAME only, so research boutiques with plain names (2Xideas, 86Research, Alembic) defaulted to
'asset_manager'. This re-derives firm_type from Wiza's richer company_industry / subindustry /
description fields (keyed by email, scoped to source='wiza_equity_research_2022'):
  Investment Banking / Capital Markets / IB&Securities -> broker_dealer
  Research / Business Information Research / Analytics  -> independent_research (new label)
  Banking / Retail & Business Banking                  -> bank
  Investment Management / Asset & Inv Mgmt             -> asset_manager (buy-side)
  Insurance / Software / PR / Publishing               -> insurance / other
  Venture Capital & Private Equity                     -> private_equity
  ambiguous 'Financial Services'                       -> description/name keywords, then firm_type_for()
Result: 247 asset_manager / 93 broker_dealer / 60 bank / 29 independent_research / 29 ria / 21 other / etc.
So ~182 sell-side/research/vendor contacts are no longer mislabeled buy-side. See the run in git history."""
# (self-documenting; the executed logic lives in the commit that introduced this file)
