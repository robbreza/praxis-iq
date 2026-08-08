"""Pin the seeder's IR-Inbox model wiring: seed_inbox_model() clears any prior copy of the
illustrative NLKP self-model (queue items + documents), stores the freshly-built document, and
enqueues a pending model review item linked to it — leaving unrelated inbox items alone. The
documents layer (SQL) is mocked; the queue runs on the in-memory db (mem_db)."""
from core import demo_model, documents, inbox_queue
import scripts.seed_illustrative_tenant as seeder


def test_seed_inbox_model_is_idempotent_and_links_doc(mem_db, monkeypatch):
    CID = "demo"
    # A stale copy of THIS model (should be cleared) + an unrelated item (should survive).
    mem_db[(CID, "inbox_queue.json")] = [
        {"id": "old", "category": "model", "filename": demo_model.FILENAME, "doc_id": 5},
        {"id": "keep", "category": "shareholder_inquiry", "filename": None, "doc_id": None},
    ]

    deleted = []
    monkeypatch.setattr(documents, "list_documents",
                        lambda **k: [{"id": 5, "filename": demo_model.FILENAME}])
    monkeypatch.setattr(documents, "delete_document",
                        lambda did, **k: deleted.append(did))
    saved = {}

    def _save_document(**kw):
        saved.update(kw)
        return 99
    monkeypatch.setattr(documents, "save_document", _save_document)

    enq = {}

    def _enqueue(**kw):
        enq.update(kw)
        return "new-id"
    monkeypatch.setattr(inbox_queue, "enqueue_item", _enqueue)

    doc_id = seeder.seed_inbox_model(CID)

    # stale document + stale queue item cleared; unrelated item preserved
    assert 5 in deleted
    remaining = mem_db[(CID, "inbox_queue.json")]
    assert [it["id"] for it in remaining] == ["keep"]

    # fresh document stored from the freshly-built workbook, tagged to the analyst
    assert doc_id == 99
    assert saved["doc_type"] == "model" and saved["filename"] == demo_model.FILENAME
    assert saved["firm"] == demo_model.FIRM and saved["contact"] == demo_model.ANALYST
    assert saved["file_bytes"][:2] == b"PK"          # a real .xlsx, not a placeholder

    # pending review item enqueued and LINKED to the new document
    assert enq["category"] == "model" and enq["doc_id"] == 99
    assert enq["filename"] == demo_model.FILENAME
    assert enq["extracted"]["price_target"] == 42.70 and enq["extracted"]["period"] == "Q2 2026E"
