"""Pin the co-ownership aggregation core (Spec 14b): revealed peers come only from FOCUSED, fundamental
holders; the issuer itself, broad ETFs, and mega-caps-via-index-books are excluded. Pure logic, no EDGAR."""
from lighthouse import coownership as co


def _pos(issuer, cusip, value):
    return {"issuer": issuer, "cusip": cusip, "value": value}


def test_mechanical_classifier():
    assert co.is_mechanical("CITADEL ADVISORS LLC")
    assert co.is_mechanical("Vanguard Capital Management LLC")
    assert not co.is_mechanical("Perkins Capital Management Inc")


def test_focused_holders_define_peers_megacaps_suppressed():
    # a focused small-cap fund: USIO + two small-cap peers
    focused = dict(filer="Perkins Capital", mechanical=False, positions=[
        _pos("USIO INC", "90403W101", 30), _pos("PAYMENT PEER A", "AAA000000", 40),
        _pos("PAYMENT PEER B", "BBB000000", 30)])
    # a mechanical index book: 1000-ish mega-cap names (represented by a few big ones) — must NOT count
    mech = dict(filer="Renaissance Technologies LLC", mechanical=True,
                positions=[_pos("NVIDIA CORP", "67066G104", 500), _pos("APPLE INC", "037833100", 500),
                           _pos("USIO INC", "90403W101", 1)])
    out = co.aggregate([focused, mech], issuer_ticker="USIO", max_positions=400, top=12)
    names = [p["issuer"] for p in out["peers"]]
    assert "PAYMENT PEER A" in names and "PAYMENT PEER B" in names   # from the focused fund
    assert not any("USIO" in n for n in names)                       # issuer itself excluded
    assert not any("NVIDIA" in n or "APPLE" in n for n in names)     # mega-caps came only via the mech book
    assert out["n_focused"] == 1 and out["n_mechanical"] == 1


def test_etf_and_issuer_excluded_and_broad_book_dropped():
    broad = dict(filer="Whittier Trust Co", mechanical=False,
                 positions=[_pos("USIO INC", "90403W101", 10)] + [_pos(f"NAME {i}", f"C{i:08d}", 5) for i in range(500)])
    focused = dict(filer="Kopp", mechanical=False, positions=[
        _pos("SPDR S&P 500 ETF", "78462F103", 50), _pos("REAL PEER", "RRR000000", 20),
        _pos("USIO INC", "90403W101", 15)])
    out = co.aggregate([broad, focused], issuer_ticker="USIO", max_positions=400, top=12)
    names = [p["issuer"] for p in out["peers"]]
    assert "REAL PEER" in names
    assert not any("SPDR" in n or "S&P 500" in n for n in names)     # broad ETF excluded
    assert out["n_focused"] == 1                                     # 500-name book exceeds max_positions
