"""Lighthouse Phase 0 — the point-in-time (no-look-ahead) spine.

The single non-negotiable invariant of the whole system: when Lighthouse explains a move as of a
historical instant, it may see ONLY facts that were knowable at that instant. The gate is a fact's
KNOWLEDGE timestamp (when it became public/knowable), NOT its content date — a 10-Q covering the
quarter ending Mar 31 filed on May 5 is knowable on May 5, not Mar 31. Every Lighthouse time series
and event therefore carries a `knowledge_ts`, and all reads pass through `AsOf.visible()`.

This module is deliberately tiny and dependency-free: it is a discipline, not a feature. Every later
engine (attribution, residual, events, flow, fusion) fetches through an AsOf so a backtest cannot
leak the future, and historical replay reproduces exactly what was knowable at a chosen instant.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone


class PointInTimeError(RuntimeError):
    """Raised when code attempts to read a fact whose knowledge_ts is after the active as-of."""


def _utc(ts) -> datetime:
    if isinstance(ts, str):
        ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    if not isinstance(ts, datetime):
        raise TypeError(f"expected datetime/ISO str, got {type(ts).__name__}")
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


@dataclass(frozen=True)
class AsOf:
    """An immutable knowledge horizon. All data access for a replay is gated to `<= as_of`."""
    as_of: datetime

    def __post_init__(self):
        object.__setattr__(self, "as_of", _utc(self.as_of))

    def knows(self, knowledge_ts) -> bool:
        """True iff a fact stamped `knowledge_ts` was knowable at this horizon."""
        return _utc(knowledge_ts) <= self.as_of

    def visible(self, records, knowledge_ts_key="knowledge_ts"):
        """Filter an iterable of dict-like records to those knowable at the horizon. Records missing
        a knowledge_ts are DROPPED (fail-closed) — an unstamped fact cannot be proven point-in-time."""
        out = []
        for r in records:
            kts = r.get(knowledge_ts_key) if hasattr(r, "get") else None
            if kts is not None and self.knows(kts):
                out.append(r)
        return out

    def assert_pit(self, knowledge_ts, what="fact"):
        """Hard guard: raise PointInTimeError if a fact would leak the future into the replay."""
        if not self.knows(knowledge_ts):
            raise PointInTimeError(
                f"look-ahead: {what} knowable at {_utc(knowledge_ts).isoformat()} "
                f"is not visible as of {self.as_of.isoformat()}")

    def where_sql(self, column="knowledge_ts", param="%s"):
        """SQL fragment + bind value to gate a query point-in-time: (fragment, value)."""
        return f"{column} <= {param}", self.as_of


def sql_gate(as_of: AsOf, column="knowledge_ts", param="%s"):
    """Convenience for query builders: returns (\"col <= %s\", as_of_value)."""
    return as_of.where_sql(column, param)
