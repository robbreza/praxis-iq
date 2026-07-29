"""Lighthouse — peer install (the onboarding entry point).

One call to build a new client's full peer picture, so everything we built for USIO is a repeatable
install for client #3+. Runs the fundamental discovery (core.peer_discovery, via the co-movement
candidate universe) and the three revealed-peer lenses, then the three-tier synthesis:

    fundamental (SIC screen + 10-K + proxy) → candidate universe
    → co-ownership (13F) · coverage (analysts) · co-movement (returns)   [the revealed lenses]
    → peer-tier synthesis (trading vs narrative vs fundamental)

Heavy (EDGAR 13F + SIC screen + yfinance loads), so it's an on-demand onboarding step, not a render.
Order matters: coverage + co-ownership run first so the co-movement candidate universe can seed from
the coverage tickers. Each lens is best-effort and caches its own result; the page reads the caches.
"""
from __future__ import annotations


def install(client_id="usio", issuer="USIO") -> dict:
    """Refresh every peer lens for a client and return a compact summary + the synthesis."""
    report = {"client_id": client_id, "issuer": issuer, "steps": {}}

    def _step(name, fn):
        try:
            r = fn()
            report["steps"][name] = {"ok": not (isinstance(r, dict) and r.get("error")),
                                     "error": (r or {}).get("error") if isinstance(r, dict) else None}
            return r
        except Exception as e:
            report["steps"][name] = {"ok": False, "error": repr(e)}
            return None

    from lighthouse import coverage, coownership, comovement, peer_synthesis
    _step("coverage", lambda: coverage.refresh_cache(client_id, issuer))       # cheap (internal data)
    _step("coownership", lambda: coownership.refresh_cache(client_id, issuer))  # heavy (EDGAR 13F)
    _step("comovement", lambda: comovement.refresh_cache(client_id, issuer))    # heavy (SIC + yfinance)
    syn = _step("synthesis", lambda: peer_synthesis.load_and_synthesize(client_id))
    report["synthesis"] = syn
    report["ok"] = all(s.get("ok") for s in report["steps"].values())
    return report


if __name__ == "__main__":
    import sys
    from lighthouse import peer_synthesis
    cid = sys.argv[1] if len(sys.argv) > 1 else "usio"
    tk = sys.argv[2] if len(sys.argv) > 2 else "USIO"
    rep = install(cid, tk)
    print(f"[peer-install] {tk}: " + " · ".join(f"{k}={'ok' if v['ok'] else 'FAIL'}"
                                                for k, v in rep["steps"].items()))
    print(peer_synthesis.render(rep.get("synthesis") or {}))
