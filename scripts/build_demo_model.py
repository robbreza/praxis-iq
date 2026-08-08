"""Rebuild the illustrative demo tenant's sell-side analyst model in place.

Regenerates the clean model .xlsx (core/demo_model.py) and writes it over the stored document, so
the IR Inbox "model" attachment pulls up a legible, properly-encoded spreadsheet. A full reseed
(scripts/seed_illustrative_tenant.py) already produces this; this script is the targeted "just fix
the model file on the running demo without reseeding everything" path.

Idempotent: finds the demo tenant's `model` document and replaces its bytes (same doc_id, so the
inbox queue item keeps resolving), and syncs the queue item's displayed filename. Run from root:

    python scripts/build_demo_model.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.demo_model import CONTENT_TYPE, FILENAME, FIRM, build_model_xlsx  # noqa: E402

CID = "demo"


def main():
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # so .env resolves
    import core.security as security
    security.load_environment()
    import config.client_config as cc
    from core import db, documents

    cc.reload_registry()
    if CID not in cc.CLIENT_REGISTRY:
        print(f"[demo model] tenant '{CID}' not found — run scripts/seed_illustrative_tenant.py first.")
        return 1
    cc.set_active_client_id(CID)

    doc = documents.get_latest_document(firm=FIRM, doc_type="model", client_id=CID)
    if not doc:
        docs = documents.list_documents(doc_type="model", client_id=CID)
        doc = docs[0] if docs else None
    if not doc:
        print("[demo model] no existing 'model' document found for the demo tenant; nothing to replace.")
        return 1

    xlsx = build_model_xlsx()
    ok = documents.update_document_bytes(doc["id"], xlsx, filename=FILENAME,
                                         content_type=CONTENT_TYPE, client_id=CID)
    print(f"[demo model] {'updated' if ok else 'FAILED to update'} doc_id={doc['id']} "
          f"-> {FILENAME} ({len(xlsx):,} bytes), clean Unicode.")

    queue = db.load_json("inbox_queue.json", [], client_id=CID) or []
    changed = 0
    for it in queue:
        if it.get("doc_id") == doc["id"] and it.get("filename") != FILENAME:
            it["filename"] = FILENAME
            changed += 1
    if changed:
        db.save_json("inbox_queue.json", queue, client_id=CID)
        print(f"[demo model] synced {changed} inbox-queue item filename(s) -> {FILENAME}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
