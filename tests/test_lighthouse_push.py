"""Pin the push pure logic (no DB/network): VAPID keys are well-formed, subscription input is
validated before any DB call, and tier gating decides push before touching the network."""
import base64
from datetime import date
from lighthouse import push


def test_generate_keys_shape():
    k = push._generate_keys()
    assert "PRIVATE KEY" in k["private_pem"]
    raw = base64.urlsafe_b64decode(k["public"] + "=" * (-len(k["public"]) % 4))
    assert len(raw) == 65 and raw[0] == 0x04         # uncompressed P-256 point
    assert push._generate_keys()["public"] != k["public"]   # random each time


def test_save_subscription_rejects_incomplete_without_db():
    # Missing keys → returns False before ever opening a connection (so this is DB-free).
    assert push.save_subscription("usio", {"endpoint": "https://x/y"}) is False
    assert push.save_subscription("usio", {"keys": {"p256dh": "a", "auth": "b"}}) is False
    assert push.save_subscription("usio", {}) is False


def _v(abn, expl, actual=-0.062):
    return dict(ticker="USIO", day=date(2026, 7, 28), actual=actual, expected=-0.011, residual=-0.041,
                rarity=0.9, unexplained_pct=0.66, abnormality_conf=abn, explanation_conf=expl,
                drivers=[dict(cls="unexplained", label="Unexplained", detail="x", link=None)])


def test_tier_gating_skips_routine_before_network():
    # ROUTINE → below the 'important' floor → returns without any send/DB/network call.
    out = push.maybe_push_verdict(_v("ROUTINE", "LOW"))
    assert out["sent"] == 0 and out.get("reason") == "below_floor" and out["tier"] == "monitoring"
