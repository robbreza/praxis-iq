"""Lighthouse — IR market-intelligence engine answering "why is the stock moving today?"

Multi-client, ticker-agnostic, configuration-driven. Built as a module inside the Praxis platform so
it reuses the existing SEC-filing parsing, peer construction, 13F holder + CRM data, market_data, and
multi-tenant client_id isolation rather than rebuilding them.

Phase 0 (this commit): the no-look-ahead spine (`replay.AsOf`), the DB schema (`schema.sql`), and the
USIO client config. See docs/lighthouse/ for the governing specs and the phased build plan.

Design invariant: every conclusion is reproducible, traceable to evidence, and computed strictly
point-in-time. The system never asserts causation when the evidence is insufficient — it separates
what happened, what's explained, what's unexplained, how unusual it is, and how confident it is.
"""
from lighthouse.replay import AsOf, PointInTimeError, sql_gate  # noqa: F401

__all__ = ["AsOf", "PointInTimeError", "sql_gate"]
__version__ = "0.0.1"  # Phase 0 scaffold
