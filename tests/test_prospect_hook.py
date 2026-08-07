"""Pin core.prospect_hook: the two-quarter 13F diff, top-mover ranking by dollar impact,
the metro trend, the deterministic hook copy, and the PIL chart — SEC bulk mocked, so no
network and no real dataset download."""
import pytest

from core import prospect_hook as ph
from core import sec_filings

_CUR = [
    {"cik": "1", "filer": "Alpha Capital", "city": "Boston", "state": "MA", "shares": 1_500_000, "value": 75_000_000},
    {"cik": "2", "filer": "Beta Advisors", "city": "Boston", "state": "MA", "shares": 500_000, "value": 25_000_000},
    {"cik": "3", "filer": "Gamma Partners", "city": "New York", "state": "NY", "shares": 300_000, "value": 15_000_000},
    {"cik": "5", "filer": "Epsilon Management", "city": "Boston", "state": "MA", "shares": 900_000, "value": 45_000_000},
]
_PRI = [
    {"cik": "1", "filer": "Alpha Capital", "city": "Boston", "state": "MA", "shares": 1_000_000, "value": 50_000_000},
    {"cik": "2", "filer": "Beta Advisors", "city": "Boston", "state": "MA", "shares": 500_000, "value": 25_000_000},
    {"cik": "3", "filer": "Gamma Partners", "city": "New York", "state": "NY", "shares": 800_000, "value": 40_000_000},
    {"cik": "4", "filer": "Delta Trust", "city": "Omaha", "state": "NE", "shares": 200_000, "value": 10_000_000},
]


@pytest.fixture
def mocked(mem_db, monkeypatch):
    monkeypatch.setattr(sec_filings, "_recent_13f_datasets",
                        lambda n=2: [("u_cur", "01mar2026-31may2026"), ("u_pri", "01dec2025-28feb2026")])
    calls = {"n": 0}

    def fake_bulk(pairs, dataset=None, save=True):
        calls["n"] += 1
        tk = pairs[0][0]
        holders = _CUR if dataset[1] == "01mar2026-31may2026" else _PRI
        return {tk: {"quarter": dataset[1], "holders": [dict(h) for h in holders]}}

    monkeypatch.setattr(sec_filings, "refresh_13f_bulk_all", fake_bulk)
    return calls


def test_prepare_diffs_and_ranks(mocked):
    d = ph.prepare("AMKR", "Amkor Technology")
    assert d["error"] is None and d["n_holders"] == 4
    # ranked by |delta_value|: Epsilon (new +$45M), Alpha (+$25M), Gamma (-$25M), Delta (exit -$10M)
    assert [c["filer"] for c in d["top_changes"]] == [
        "Epsilon Management", "Alpha Capital", "Gamma Partners", "Delta Trust"]
    dirs = {c["filer"]: c["direction"] for c in d["top_changes"]}
    assert dirs == {"Epsilon Management": "new", "Alpha Capital": "added",
                    "Gamma Partners": "trimmed", "Delta Trust": "exited"}
    assert dirs.get("Beta Advisors") is None                 # unchanged holder is not a mover


def test_metro_trend_counts_top_movers(mocked):
    d = ph.prepare("AMKR", "Amkor Technology")
    # Epsilon + Alpha are both Boston among the 4 movers (NDR canonical label)
    assert d["metro_trend"]["metro"] == "Boston / New England"
    assert d["metro_trend"]["count"] == 2 and d["metro_trend"]["of"] == 4


def test_hook_text_is_factual(mocked):
    d = ph.prepare("AMKR", "Amkor Technology")
    t = ph.hook_text(d)
    assert "last two 13F quarters" in t
    assert "opened a new position" in t and "$45M" in t     # Epsilon new position
    assert "Boston / New England funds" in t                # metro trend line


def test_metro_chart_png_bytes(mocked):
    d = ph.prepare("AMKR", "Amkor Technology")
    png = ph.metro_chart_png(d)
    assert png and png[:8] == b"\x89PNG\r\n\x1a\n"           # valid PNG signature


def test_active_moves_chart_png_bytes(mocked):
    d = ph.prepare("AMKR", "Amkor Technology")
    png = ph.active_moves_chart_png(d)
    assert png and png[:8] == b"\x89PNG\r\n\x1a\n"           # the visual of the hook renders


def test_net_posture_and_board_briefing(mocked):
    # AMKR fixture: Epsilon(new) + Alpha(added) vs Gamma(trimmed) + Delta(exited) => mixed 2/2
    d = ph.prepare("AMKR", "Amkor Technology")
    p = ph.net_posture(d)
    assert p == {"label": "mixed", "accumulating": 2, "trimming": 2}
    b = ph.briefing_text(d)
    assert b.startswith("Across the")                        # board-toned, not the outreach "I ran…"
    assert "adding or initiating" in b and "trimming or exiting" in b


def test_prepare_is_cached(mocked):
    ph.prepare("AMKR", "Amkor Technology")
    n_after_first = mocked["n"]
    ph.prepare("AMKR", "Amkor Technology")                   # same quarter -> served from cache
    assert mocked["n"] == n_after_first                      # no second pair of bulk pulls
    ph.prepare("AMKR", "Amkor Technology", force=True)       # force re-pulls
    assert mocked["n"] > n_after_first


def test_fund_family_is_netted(mem_db, monkeypatch):
    # Vanguard files under several entities and reshuffles between them: a naive diff shows a big
    # "exit" next to two "new positions". Netting the family must show ONE line, truly added.
    cur = [
        {"cik": "10", "filer": "VANGUARD CAPITAL MANAGEMENT LLC", "city": "Malvern", "state": "PA",
         "shares": 900_000, "value": 489_000_000},
        {"cik": "11", "filer": "VANGUARD PORTFOLIO MANAGEMENT LLC", "city": "Malvern", "state": "PA",
         "shares": 800_000, "value": 410_000_000},
        {"cik": "12", "filer": "Bridgewater Associates, LP", "city": "Westport", "state": "CT",
         "shares": 100_000, "value": 68_000_000},
    ]
    pri = [
        {"cik": "9", "filer": "VANGUARD GROUP INC", "city": "Valley Forge", "state": "PA",
         "shares": 1_400_000, "value": 620_000_000},
        {"cik": "12", "filer": "Bridgewater Associates, LP", "city": "Westport", "state": "CT",
         "shares": 50_000, "value": 34_000_000},
    ]
    monkeypatch.setattr(sec_filings, "_recent_13f_datasets",
                        lambda n=2: [("u_cur", "01mar2026-31may2026"), ("u_pri", "01dec2025-28feb2026")])
    monkeypatch.setattr(sec_filings, "refresh_13f_bulk_all",
                        lambda pairs, dataset=None, save=True: {pairs[0][0]: {
                            "holders": [dict(h) for h in (cur if dataset[1].startswith("01mar") else pri)]}})
    d = ph.prepare("AMKR", "Amkor Technology")
    vg = [c for c in d["top_changes"] if c["filer"] == "Vanguard"]
    assert len(vg) == 1 and vg[0]["family"] is True
    # 489M + 410M (cur) vs 620M (prior) => +$279M, ADDED (not exited, not two new positions)
    assert vg[0]["direction"] == "added" and vg[0]["delta_value"] == 279_000_000
    assert "across its funds" in ph.hook_text(d)


def test_active_moves_lead_over_passive(mem_db, monkeypatch):
    # Passive giants have the biggest dollar swings, but the hook must lead with the ACTIVE
    # managers (the conviction signal), not Vanguard/Morgan Stanley flow.
    cur = [
        {"cik": "1", "filer": "VANGUARD GROUP INC", "city": "Malvern", "state": "PA",
         "shares": 10_000_000, "value": 5_000_000_000},
        {"cik": "2", "filer": "MORGAN STANLEY", "city": "New York", "state": "NY",
         "shares": 5_000_000, "value": 2_000_000_000},
        {"cik": "3", "filer": "Norges Bank", "city": "Oslo", "state": "Q8",
         "shares": 2_000_000, "value": 400_000_000},                    # active, trimmed
        {"cik": "4", "filer": "Bridgewater Associates, LP", "city": "Westport", "state": "CT",
         "shares": 1_000_000, "value": 300_000_000},                    # active, added
    ]
    pri = [
        {"cik": "1", "filer": "VANGUARD GROUP INC", "city": "Valley Forge", "state": "PA",
         "shares": 6_000_000, "value": 3_000_000_000},
        {"cik": "2", "filer": "MORGAN STANLEY", "city": "New York", "state": "NY",
         "shares": 2_000_000, "value": 800_000_000},
        {"cik": "3", "filer": "Norges Bank", "city": "Oslo", "state": "Q8",
         "shares": 4_000_000, "value": 800_000_000},
        {"cik": "4", "filer": "Bridgewater Associates, LP", "city": "Westport", "state": "CT",
         "shares": 500_000, "value": 150_000_000},
    ]
    monkeypatch.setattr(sec_filings, "_recent_13f_datasets",
                        lambda n=2: [("u_cur", "01mar2026-31may2026"), ("u_pri", "01dec2025-28feb2026")])
    monkeypatch.setattr(sec_filings, "refresh_13f_bulk_all",
                        lambda pairs, dataset=None, save=True: {pairs[0][0]: {
                            "holders": [dict(h) for h in (cur if dataset[1].startswith("01mar") else pri)]}})
    d = ph.prepare("XYZ", "Example Semiconductor")
    assert all(not c["passive"] for c in d["top_active"])               # active view excludes flow
    assert [c["filer"] for c in d["top_active"]] == ["Norges Bank", "Bridgewater Associates, LP"]
    t = ph.hook_text(d)
    assert "active-manager moves" in t
    assert "Norges Bank" in t and "Bridgewater" in t
    assert "Vanguard" not in t and "Morgan Stanley" not in t            # passive giants not in the lead


def test_refresh_client_briefings_only_pulls_stale(monkeypatch):
    # Quarterly auto-refresh: pull only clients whose cache is stale/missing; skip the demo tenant;
    # never re-pull a briefing that's already on the latest quarter.
    calls = []
    monkeypatch.setattr(ph, "latest_quarter_label", lambda: "01mar2026-31may2026")
    cache = {
        "USIO": {"quarter": "01mar2026-31may2026"},          # current — must NOT pull
        "SARO": {"quarter": "01dec2025-28feb2026"},          # stale (old quarter) — pull
        # AMKR: no cache -> stale -> pull
    }
    monkeypatch.setattr(ph, "get_cached", lambda tk, client_id=None: cache.get(tk))

    def fake_prepare(tk, name, force=False, top_n=10, client_id=None):
        calls.append(tk)
        return {"quarter": "01mar2026-31may2026", "error": None}
    monkeypatch.setattr(ph, "prepare", fake_prepare)

    clients = [("usio", "USIO", "Usio, Inc."), ("saro", "SARO", "StandardAero, Inc."),
               ("ceva", "AMKR", "Amkor"), ("demo", "NLKP", "Northlake")]
    by = {r["client"]: r["status"] for r in ph.refresh_client_briefings(clients)}
    assert by == {"usio": "current", "saro": "refreshed", "ceva": "refreshed", "demo": "skipped"}
    assert set(calls) == {"SARO", "AMKR"}                    # only the stale ones pulled; demo skipped


def test_coverage_gap_false_new_is_dropped(mem_db, monkeypatch):
    # A holder can look "new" only because the prior quarter's bulk line was missed (Whittier/USIO).
    # The guard checks the filer's OWN history and drops the false initiation, keeps genuine ones.
    cur = [
        {"cik": "100", "filer": "Steady Trust CO", "city": "Boston", "state": "MA",
         "shares": 2_700_000, "value": 3_200_000},          # falsely "new" (coverage gap)
        {"cik": "200", "filer": "Real Buyer LP", "city": "New York", "state": "NY",
         "shares": 1_000_000, "value": 40_000_000},         # genuinely new
    ]
    pri = [
        {"cik": "300", "filer": "Old Holder LLC", "city": "Chicago", "state": "IL",
         "shares": 500_000, "value": 20_000_000},           # genuinely exits next quarter
    ]
    monkeypatch.setattr(sec_filings, "_recent_13f_datasets",
                        lambda n=2: [("u", "01mar2026-31may2026"), ("u2", "01dec2025-28feb2026")])
    monkeypatch.setattr(sec_filings, "refresh_13f_bulk_all",
                        lambda pairs, dataset=None, save=True: {pairs[0][0]: {"cusip": "12345",
                            "holders": [dict(h) for h in (cur if dataset[1].startswith("01mar") else pri)]}})

    def fake_hist(cik, cusip=None, issuer_token=None, quarters=6, **kw):
        cik = int(cik)
        if cik == 100:                                       # established across many filings
            return {"history": [{"shares": 2_700_000}, {"shares": 2_800_000}, {"shares": 2_800_000}]}
        if cik == 200:                                       # only the current filing -> genuine new
            return {"history": [{"shares": 1_000_000}]}
        if cik == 300:                                       # latest filing empty -> genuine exit
            return {"history": [{"shares": None}, {"shares": 500_000}]}
        return {"history": []}
    monkeypatch.setattr(sec_filings, "holder_history", fake_hist)

    d = ph.prepare("XX", "Example Inc")
    filers = [c["filer"] for c in d["top_changes"]]
    assert "Steady Trust CO" not in filers                   # false 'new' dropped
    assert "Real Buyer LP" in filers                         # genuine new kept
    assert "Old Holder LLC" in filers                        # genuine exit kept
    assert d["coverage_dropped"] == 1


def test_no_holders_returns_error(mem_db, monkeypatch):
    monkeypatch.setattr(sec_filings, "_recent_13f_datasets",
                        lambda n=2: [("u_cur", "01mar2026-31may2026"), ("u_pri", "01dec2025-28feb2026")])
    monkeypatch.setattr(sec_filings, "refresh_13f_bulk_all",
                        lambda pairs, dataset=None, save=True: {pairs[0][0]: {"holders": []}})
    d = ph.prepare("ZZZZ", "Nowhere Inc")
    assert d["error"] and "No 13F holders" in d["error"]
    assert ph.hook_text(d) == ""                             # no hook when no data
