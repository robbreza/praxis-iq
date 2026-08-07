"""Pin core.ndr_inbound: threading an analyst reply back onto its NDR request — build_index,
the match() resolution (threading > sender), dedupe, and an end-to-end poll with a fake IMAP.
In-memory store; no network."""
from email.message import EmailMessage

from core import ndr_inbound, ndr_correspondence, zoho_mail

SENT_MID = "<sent-abc123@praxispointir.com>"


def _seed(mem_db):
    mem_db[("t", "ndr_requests.json")] = [{
        "id": "r1", "analyst": "Jane Doe", "firm": "Fidelity", "city": "Boston",
        "response_status": "replied",
        "correspondence": [{"direction": "out", "to": "jane@fidelity.com",
                            "message_id": SENT_MID, "subject": "Re: your meeting request"}],
    }]


def test_match_threads_by_message_id(mem_db):
    _seed(mem_db)
    idx = ndr_inbound.build_index(["t"])
    hit = ndr_inbound.match({"message_id": "<r1@x>", "in_reply_to": SENT_MID,
                             "references": None, "from_email": "someone@else.com"}, idx)
    assert hit == ("t", "r1")                       # threading wins even if sender is unknown


def test_match_falls_back_to_sender(mem_db):
    _seed(mem_db)
    idx = ndr_inbound.build_index(["t"])
    hit = ndr_inbound.match({"message_id": "<r2@x>", "in_reply_to": None, "references": None,
                             "from_email": "Jane@Fidelity.com"}, idx)     # case-insensitive
    assert hit == ("t", "r1")


def test_match_dedupes_and_misses(mem_db):
    _seed(mem_db)
    # an inbound already recorded is skipped
    mem_db[("t", "ndr_requests.json")][0]["correspondence"].append(
        {"direction": "in", "message_id": "<seen@x>"})
    idx = ndr_inbound.build_index(["t"])
    assert ndr_inbound.match({"message_id": "<seen@x>", "in_reply_to": SENT_MID,
                              "references": None, "from_email": "jane@fidelity.com"}, idx) is None
    assert ndr_inbound.match({"message_id": "<new@x>", "in_reply_to": None, "references": None,
                              "from_email": "stranger@nowhere.com"}, idx) is None


class _FakeIMAP:
    def __init__(self, raws):
        self.raws = raws

    def select(self, box):
        return ("OK", [b"1"])

    def search(self, charset, query):
        return ("OK", [b" ".join(str(i + 1).encode() for i in range(len(self.raws)))])

    def fetch(self, num, spec):
        return ("OK", [(num, self.raws[int(num) - 1])])

    def logout(self):
        pass


def _reply_bytes(in_reply_to=SENT_MID, mid="<reply-999@fidelity.com>", frm="Jane Doe <jane@fidelity.com>"):
    m = EmailMessage()
    m["From"] = frm
    m["Subject"] = "Re: your meeting request"
    m["Message-ID"] = mid
    if in_reply_to:
        m["In-Reply-To"] = in_reply_to
    m.set_content("Tuesday at 2pm works for us.")
    return m.as_bytes()


def test_poll_threads_reply_and_is_idempotent(mem_db, monkeypatch):
    _seed(mem_db)
    monkeypatch.setattr(zoho_mail, "is_configured", lambda: True)
    monkeypatch.setattr(zoho_mail, "imap_login", lambda: (_FakeIMAP([_reply_bytes()]), None))

    r = ndr_inbound.poll_replies(client_ids=["t"])
    assert r["ok"] and r["matched"] == 1 and r["checked"] == 1
    req = mem_db[("t", "ndr_requests.json")][0]
    ins = [c for c in req["correspondence"] if c["direction"] == "in"]
    assert len(ins) == 1
    assert ins[0]["from"] == "jane@fidelity.com" and ins[0]["message_id"] == "<reply-999@fidelity.com>"
    assert ndr_correspondence.status(req) == "replied"     # WE still replied; their note doesn't change it

    # a second poll of the same message must not duplicate
    r2 = ndr_inbound.poll_replies(client_ids=["t"])
    assert r2["matched"] == 0
    ins2 = [c for c in mem_db[("t", "ndr_requests.json")][0]["correspondence"] if c["direction"] == "in"]
    assert len(ins2) == 1


def test_poll_inert_without_zoho(mem_db, monkeypatch):
    monkeypatch.setattr(zoho_mail, "is_configured", lambda: False)
    assert ndr_inbound.poll_replies(client_ids=["t"])["ok"] is False
