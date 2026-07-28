"""Pin the telemetry pure logic: token signing round-trips, tampered/garbage tokens are rejected,
url helpers format correctly, and the digest HTML embeds the open-pixel + tracked CTA only when
tracking urls are supplied. No DB or network here."""
from datetime import date
from lighthouse import telemetry, digest


def test_token_round_trip():
    for did in (1, 42, 999999):
        assert telemetry.parse_token(telemetry.make_token(did)) == did


def test_tampered_token_rejected():
    tok = telemetry.make_token(7)
    body, sig = tok.split(".", 1)
    assert telemetry.parse_token(f"{body}.{'0'*len(sig)}") is None   # bad signature
    assert telemetry.parse_token("garbage") is None
    assert telemetry.parse_token("") is None


def test_url_helpers():
    assert telemetry.pixel_url("https://x.io/", 5).startswith("https://x.io/lh/o/")
    assert telemetry.click_url("https://x.io", 5).startswith("https://x.io/lh/c/")
    assert telemetry.pixel_url("", 5) is None          # no app_url → no tracking url
    assert telemetry.click_url("https://x.io", None) is None


def _v():
    return dict(ticker="USIO", day=date(2026, 7, 28), actual=-0.062, expected=-0.011, residual=-0.041,
                rarity=0.9, unexplained_pct=0.66, abnormality_conf="HIGH", explanation_conf="LOW",
                drivers=[dict(cls="unexplained", label="Unexplained", detail="x", link=None)],
                found=[], not_found=["none"], technical="mixed")


def test_html_embeds_pixel_and_tracked_cta_only_when_supplied():
    plain = digest.render_html(_v(), app_url="https://x.io")
    assert "width=\"1\"" not in plain and "/lh/o/" not in plain    # no pixel without a tracking url
    tracked = digest.render_html(_v(), app_url="https://x.io",
                                 cta_url="https://x.io/lh/c/tok", pixel_url="https://x.io/lh/o/tok")
    assert "https://x.io/lh/o/tok" in tracked and 'width="1"' in tracked   # pixel present
    assert "https://x.io/lh/c/tok" in tracked                              # CTA routes through click endpoint
