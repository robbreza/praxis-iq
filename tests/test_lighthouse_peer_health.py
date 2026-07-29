"""Pin the peer-health verdict (Spec 13.4): the tiering logic — stale/no-gp/oversized/thin/healthy —
and that a 'reference' name is exempt from the oversized downgrade (an analyst's comp-sheet category
name is a legitimate reference peer, not an error). Pure logic, no EDGAR."""
from lighthouse import peer_health as ph


def test_stale_when_no_live_data():
    assert ph.verdict(current=False, ev_m=None, gp_status="ok", issuer_ev_m=50, dollar_adv=1e6)[0] == "STALE"
    assert ph.verdict(current=True, ev_m=None, gp_status="ok", issuer_ev_m=50, dollar_adv=1e6)[0] == "STALE"


def test_no_gross_profit_line():
    assert ph.verdict(True, 100, "no_gross_profit_line", 50, 1e6)[0] == "NO-GP"


def test_oversized_and_reference_exempt():
    v, note = ph.verdict(True, 2000, "ok", 50, 1e7)                    # 40× the issuer
    assert v == "OVERSIZED" and "×" in note
    # a name already tagged reference is not re-flagged — it's reference by design
    assert ph.verdict(True, 2000, "ok", 50, 1e7, tier="reference")[0] == "HEALTHY"


def test_thin_liquidity():
    assert ph.verdict(True, 100, "ok", 50, 100_000)[0] == "THIN"       # < $0.5M/day


def test_healthy_size_and_liquid():
    assert ph.verdict(True, 100, "ok", 50, 5_000_000)[0] == "HEALTHY"  # 2× size, liquid


def test_precedence_stale_beats_all():
    # no live data dominates even if other fields look off
    assert ph.verdict(False, None, "no_gross_profit_line", 50, 1_000)[0] == "STALE"
