"""core/loop_readiness.py — is the earnings-script / Q&A loop fully lit for a client?

The loop has a chain of inputs: a confirmed speaker lineup → the CFO's Stage-1
numbers → a drafted script → (optionally) ingested research notes → an adversarial
Q&A run → a post-call transcript. Each unlocks the next stage. On the demo tenant
they're all seeded; on a real client (usio/saro) most start empty and light up as
the client provides them.

assess(client_id) reports every stage's readiness — what's present vs what's still
waiting, and what each unlocks — so the IR operator sees at a glance exactly what to
provide to light up the full loop. The UI renders the waiting ones with the shared
`waiting_signal` component. Pure reads (no writes); works for ANY client_id without
switching the active tenant.
"""
from config.client_config import get_active_client_id
from core import db, inbox_queue, speakers, transcripts


def _item_source(it):
    return it.get("source") or ("manual" if it.get("manual") else "ai")


def assess(client_id=None):
    """Return the loop's readiness for a client:
      {client_id, period, stages[], ready_required, total_required, fully_lit}
    where each stage is {key, label, optional, ready, detail, waiting_for, todo, unlocks}."""
    cid = client_id or get_active_client_id()
    period = speakers.current_period(cid)
    ss = db.load_json("script_workflow_state.json", {}, client_id=cid) or {}
    nums = ss.get("q2_numbers") or {}
    script_text = ss.get("script_text") or {}
    items = (ss.get("adversarial_qa") or {}).get("items") or []
    notes = inbox_queue.list_items_by_category("research_note", client_id=cid) or []
    rec = transcripts.get_transcript(period, cid) if period else None

    drafted = sum(1 for v in script_text.values() if (v or "").strip())
    ai_items = [it for it in items if _item_source(it) == "ai"]
    has_transcript = bool(rec and (rec.get("full_text") or "").strip())

    stages = [
        {"key": "speakers", "label": "Speaker lineup", "optional": False,
         "ready": bool(period and speakers.is_confirmed(period, cid)),
         "detail": (f"Confirmed for {period}." if period else "No reporting quarter set."),
         "waiting_for": "a confirmed speaker lineup",
         "todo": (f"Confirm the {period} lineup on Script Generation (the workflow gate)." if period
                  else "Set the client's reporting quarter, then confirm the lineup."),
         "unlocks": "responder assignment + the script workflow"},
        {"key": "cfo_numbers", "label": "CFO Stage-1 numbers", "optional": False,
         "ready": nums.get("rev") is not None,
         "detail": "Q2 actuals submitted.",
         "waiting_for": "the CFO's Stage-1 numbers",
         "todo": "CFO submits actuals on Script Generation → Stage 1.",
         "unlocks": "script drafting, the guidance engine, and the number tie-out"},
        {"key": "script", "label": "Drafted script", "optional": False,
         "ready": drafted > 0,
         "detail": f"{drafted} section(s) drafted.",
         "waiting_for": "a drafted script",
         "todo": "Draft the prepared remarks (auto-drafts once Stage-1 numbers are in).",
         "unlocks": "the adversarial Q&A pass, the tie-out, and the teleprompter"},
        {"key": "research", "label": "Research notes", "optional": True,
         "ready": len(notes) > 0,
         "detail": f"{len(notes)} note(s) ingested.",
         "waiting_for": "ingested sell-side research notes",
         "todo": "Email analyst research to the IR inbox (enriches recurring Q&A).",
         "unlocks": "research-grounded recurring questions in Q&A prep"},
        {"key": "adversarial", "label": "Adversarial Q&A run", "optional": False,
         "ready": len(ai_items) > 0,
         "detail": f"{len(items)} question(s) in the prep list.",
         "waiting_for": "an adversarial Q&A run",
         "todo": "Run 'Generate tough questions' on Q&A Prep (needs a drafted script).",
         "unlocks": "predicted questions, the prep sheet, and bank seeding"},
        {"key": "transcript", "label": "Call transcript", "optional": False,
         "ready": has_transcript,
         "detail": (f"On file for {period}." if has_transcript else "None yet."),
         "waiting_for": "a call transcript",
         "todo": (f"Upload the {period} transcript on Earnings → Call Transcripts (post-call)." if period
                  else "Upload the call transcript after the call."),
         "unlocks": "Prep-vs-Actual grading, the accuracy trend, and surprise accrual"},
    ]
    required = [s for s in stages if not s["optional"]]
    ready_required = sum(1 for s in required if s["ready"])
    return {"client_id": cid, "period": period, "stages": stages,
            "ready_required": ready_required, "total_required": len(required),
            "fully_lit": ready_required == len(required)}
