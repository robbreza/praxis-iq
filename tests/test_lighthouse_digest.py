"""Pin the digest's pure logic: tier assignment (the alert-center gate) and that every channel
renders without touching the network. Sending is deliberately NOT exercised here — dispatch() must be
fail-closed and disabled by default, which the last test asserts."""
from datetime import date
from lighthouse import digest


def _v(abn, expl, actual=-0.062, expected=-0.011, residual=-0.041, rarity=0.9, drivers=None):
    return dict(ticker="USIO", day=date(2026, 7, 28), actual=actual, expected=expected,
                residual=residual, rarity=rarity, unexplained_pct=abs(residual) / abs(actual),
                abnormality_conf=abn, explanation_conf=expl,
                drivers=drivers or [dict(cls="unexplained", label="Unexplained by current lenses",
                                         detail="idiosyncratic", link=None)],
                found=[], not_found=["No 8-K/10-Q/10-K in window."], technical="mixed trend structure")


def test_tiers_map_from_confidence():
    assert digest.priority(_v("HIGH", "LOW"))["tier"] == "critical"       # abnormal, no cause → act now
    assert digest.priority(_v("HIGH", "HIGH"))["tier"] == "important"     # abnormal but explained
    assert digest.priority(_v("MODERATE", "LOW"))["tier"] == "important"  # unusual, unconfirmed
    assert digest.priority(_v("MODERATE", "HIGH"))["tier"] == "informational"
    assert digest.priority(_v("ROUTINE", "LOW"))["tier"] == "monitoring"  # normal day, don't buzz


def test_ranks_are_ordered_for_channel_floors():
    r = [digest.priority(_v(a, e))["rank"] for a, e in
         [("ROUTINE", "LOW"), ("MODERATE", "HIGH"), ("MODERATE", "LOW"), ("HIGH", "LOW")]]
    assert r == sorted(r) and r[0] < r[-1]           # monitoring < informational < important < critical


def test_all_channels_render():
    dig = digest.build_digest(_v("HIGH", "LOW"), app_url="https://praxis-iq.onrender.com")
    assert dig["subject"].startswith("[CRITICAL] USIO")
    assert dig["subject"].isascii()                  # email header must stay ASCII
    assert "USIO" in dig["text"] and "IR action" in dig["text"]
    assert dig["sms"].isascii() and len(dig["sms"]) <= 320
    assert "<div" in dig["html"] and "praxis-iq.onrender.com" in dig["html"]


def test_ordinal_rendering():
    assert "90th-percentile" in digest.build_digest(_v("HIGH", "LOW", rarity=0.90))["text"]
    assert "81st-percentile" in digest.build_digest(_v("HIGH", "LOW", rarity=0.81))["text"]


def test_dispatch_is_disabled_by_default(monkeypatch):
    # No env configured → dispatch renders but never sends, and never raises.
    for k in ("LIGHTHOUSE_DIGEST_ENABLED", "LIGHTHOUSE_DIGEST_TO", "LIGHTHOUSE_DIGEST_SMS_TO"):
        monkeypatch.delenv(k, raising=False)
    rep = digest.dispatch(_v("HIGH", "LOW"))
    assert rep["sent"] is False and rep.get("reason") == "preview"
    assert digest.is_enabled() is False
