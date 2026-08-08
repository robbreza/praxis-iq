"""Pin the fund-lineup crosswalk's human-in-the-loop confirm/reject/restore mutations and — most
importantly — that a re-scan (bootstrap_crosswalk) NEVER clobbers a user decision (a confirmed
mapping stays, a rejected one isn't resurrected). This tombstone guarantee is what lets the auto
matcher run repeatedly without undoing the IR team's curation. Hermetic: the crosswalk store runs
on the in-memory db (mem_db); network calls (_registrant_name / _fund_registrant_norms /
series_roster) are monkeypatched."""
import core.fund_lineup as FL


def _seed(mem_db, store):
    mem_db[(FL._GLOBAL, FL._CROSSWALK_KEY)] = store


def test_confirm_locks_and_makes_usable(mem_db, monkeypatch):
    monkeypatch.setattr(FL, "_registrant_name", lambda cik: {123: "Acme Funds Trust"}.get(cik))
    # an ambiguous "review" entry is NOT used until confirmed
    _seed(mem_db, {"acme": {"ciks": [123, 456], "confidence": "review",
                            "confirmed": False, "rejected": False, "manager": "Acme Advisors"}})
    assert FL._registrant_cik("Acme Advisors") is None

    FL.confirm_entry("acme", cik=123)
    e = FL._crosswalk()["acme"]
    assert e["confirmed"] is True and e["rejected"] is False
    assert e["cik"] == 123 and e["confidence"] == "manual" and e["registrant"] == "Acme Funds Trust"
    assert FL._registrant_cik("Acme Advisors") == 123          # now resolves


def test_reject_tombstones_and_unuses(mem_db):
    _seed(mem_db, {"beta": {"cik": 789, "confidence": "high",
                            "confirmed": False, "rejected": False, "manager": "Beta Capital"}})
    assert FL._registrant_cik("Beta Capital") == 789           # a high auto-match is used

    FL.reject_entry("beta")
    e = FL._crosswalk()["beta"]
    assert e["rejected"] is True and e["confirmed"] is False
    assert FL._registrant_cik("Beta Capital") is None          # rejected is never used


def test_restore_returns_to_auto_state(mem_db):
    _seed(mem_db, {"beta": {"cik": 789, "confidence": "high",
                            "confirmed": False, "rejected": True, "manager": "Beta Capital"}})
    assert FL._registrant_cik("Beta Capital") is None

    FL.restore_entry("beta")
    e = FL._crosswalk()["beta"]
    assert e["confirmed"] is False and e["rejected"] is False
    assert FL._registrant_cik("Beta Capital") == 789           # high match usable again


def test_rescan_respects_user_decisions(mem_db, monkeypatch):
    # Offline auto-matcher: two managers each uniquely match a fund registrant.
    monkeypatch.setattr(FL, "_fund_registrant_norms", lambda: {"gamma": [100], "delta": [200]})
    monkeypatch.setattr(FL, "series_roster", lambda cik: {
        100: {"funds": ["Gamma Value"], "registrant": "Gamma Trust"},
        200: {"funds": ["Delta Growth"], "registrant": "Delta Trust"},
    }.get(cik))

    FL.bootstrap_crosswalk(["Gamma Advisors", "Delta Advisors"])
    cw = FL._crosswalk()
    assert cw["gamma"]["confidence"] == "high" and cw["delta"]["confidence"] == "high"

    # User rejects gamma, confirms delta.
    monkeypatch.setattr(FL, "_registrant_name", lambda cik: {200: "Delta Trust"}.get(cik))
    FL.reject_entry("gamma")
    FL.confirm_entry("delta")

    # Re-scan: the auto-matcher would re-add BOTH as high — the tombstones must survive.
    FL.bootstrap_crosswalk(["Gamma Advisors", "Delta Advisors"])
    cw = FL._crosswalk()
    assert cw["gamma"]["rejected"] is True                     # not resurrected
    assert cw["delta"]["confirmed"] is True                    # not clobbered
    assert FL._registrant_cik("Gamma Advisors") is None        # rejected stays unused
    assert FL._registrant_cik("Delta Advisors") == 200         # confirmed stays used


def test_crosswalk_entries_exposes_rows_with_norm(mem_db):
    _seed(mem_db, {"acme": {"cik": 123, "confidence": "high", "confirmed": True,
                            "rejected": False, "manager": "Acme Advisors"}})
    rows = FL.crosswalk_entries()
    assert len(rows) == 1 and rows[0]["norm"] == "acme" and rows[0]["confirmed"] is True
