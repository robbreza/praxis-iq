"""
scripts/seed_research_library.py — seed illustrative analyst research notes (PDF) into the
documents store for the demo tenant, so the IR Inbox → Research Library shows a believable mix of
models (already seeded) and research notes. Idempotent: skips a firm that already has a research
note. Fictional issuer NLKP (Northlake Payments) — illustrative only, never real research.

Run directly (`python scripts/seed_research_library.py`) or import seed_research_library(cid) from
the main seed. Safe to re-run.
"""
import io


def _note_pdf(firm, analyst, rating, pt, headline, paras):
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.units import inch
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_LEFT
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
    from reportlab.lib import colors

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=LETTER, topMargin=0.85 * inch, bottomMargin=0.8 * inch,
                            leftMargin=0.9 * inch, rightMargin=0.9 * inch,
                            title=f"NLKP — {firm}")
    ss = getSampleStyleSheet()
    firm_st = ParagraphStyle("firm", parent=ss["Title"], fontSize=17, spaceAfter=2, alignment=TA_LEFT)
    sub_st = ParagraphStyle("sub", parent=ss["Normal"], fontSize=9, textColor=colors.HexColor("#64748B"))
    head_st = ParagraphStyle("head", parent=ss["Heading2"], fontSize=13, spaceBefore=10, spaceAfter=4,
                             textColor=colors.HexColor("#0F172A"))
    body_st = ParagraphStyle("body", parent=ss["Normal"], fontSize=10.5, leading=15, spaceAfter=6)
    rate_st = ParagraphStyle("rate", parent=ss["Normal"], fontSize=11, spaceBefore=4, spaceAfter=8,
                             textColor=colors.HexColor("#1D4ED8"))

    story = [
        Paragraph(firm, firm_st),
        Paragraph(f"Equity Research · {analyst}", sub_st),
        Spacer(1, 6),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#E2E8F0")),
        Spacer(1, 8),
        Paragraph("Northlake Payments, Inc. (NLKP)", head_st),
        Paragraph(headline, ParagraphStyle("hl", parent=body_st, fontSize=12, leading=16)),
        Paragraph(f"<b>Rating: {rating} &nbsp;·&nbsp; Price Target: ${pt:.2f}</b>", rate_st),
    ]
    for h, p in paras:
        story.append(Paragraph(h, head_st))
        story.append(Paragraph(p, body_st))
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "Illustrative research prepared for a product demonstration. Northlake Payments (NLKP) is a "
        "fictional issuer; nothing herein is investment advice.", sub_st))
    doc.build(story)
    return buf.getvalue()


# (firm, analyst, rating, PT, filename, headline, [(section, body), ...])
_NOTES = [
    ("Ashfield Research", "Ellis Grant", "Buy", 43.0, "NLKP_Ashfield_Q2_Preview.pdf",
     "Q2 preview: net take-rate is the tell — we look for a fifth straight quarter of expansion. Reiterate Buy.",
     [("Thesis", "We continue to see Northlake as a net-revenue compounder mispriced on a gross-revenue "
                 "optic. PayFac attach is the swing factor — as more volume moves onto the integrated "
                 "payments stack, net take-rate steps up and the mix shifts toward durable, recurring "
                 "software-like economics."),
      ("The KPI we underwrite: net take-rate", "If we could watch only one line, it would be net take-rate — "
                 "the net spread Northlake keeps on integrated volume, and the single cleanest read on business "
                 "quality. We look for Q2 net take-rate of ~47 bps, up from 46 bps last quarter and ~42 bps a "
                 "year ago — a fifth consecutive quarter of expansion. On ~$3.4B of integrated volume, each "
                 "basis point is roughly $0.3M of high-incremental-margin net revenue, so it is this line, not "
                 "gross processing volume, that compounds. As integrated mix pushes past ~62% of net revenue we "
                 "see a credible path to 50+ bps by FY2027. A stall in take-rate is the one datapoint that would "
                 "break the thesis — which is exactly why we anchor our Buy to it."),
      ("Into the print", "We model Q2 net revenue of ~$25.9M and adj. EBITDA of ~$5.4M (~21% margin). Watch the "
                         "gross-to-net bridge and prepaid-float commentary — the two items the buy-side keeps flagging."),
      ("Risks", "Rate-sensitive prepaid float; concentration in a handful of ISV partners; competitive "
                "pricing on interchange-plus that could cap take-rate expansion.")]),
    ("Denby Securities", "Marta Reyes", "Buy", 45.0, "NLKP_Denby_Initiation.pdf",
     "Initiating at Buy, $45 PT: a durable net-revenue compounder with a widening ISV moat.",
     [("Why we like it", "Northlake sits at the intersection of embedded payments and vertical software. The "
                         "PayFac-as-a-service motion lets ISVs monetize payments without owning the risk stack, "
                         "and Northlake keeps the net spread. That is a structurally advantaged position."),
      ("Valuation", "Our $45 target is ~11x NTM net revenue, a modest premium we think is justified by "
                    "above-peer net-revenue growth and expanding margins."),
      ("What could go wrong", "Slower ISV onboarding, float compression, or a step-down in attach economics.")]),
    ("Westmark Partners", "Owen Pike", "Hold", 38.0, "NLKP_Westmark_Balanced_Setup.pdf",
     "Balanced setup into the print; we stay at Hold until float durability is clearer.",
     [("Our read", "We are constructive on the attach story but want another quarter of evidence that "
                   "prepaid float is not rolling over as rates normalize. The risk/reward looks balanced here."),
      ("Estimates", "We are roughly in line with the Street on Q2 net revenue and slightly below on EBITDA, "
                    "reflecting a more conservative float assumption."),
      ("Path to more constructive", "A clean gross-to-net bridge and stable float would move us off the "
                                    "sidelines.")]),
    ("Calder & Co.", "Neil Barrow", "Buy", 42.0, "NLKP_Calder_Estimate_Update.pdf",
     "Raising estimates on stronger volume; PayFac attach ahead of plan. Reiterate Buy.",
     [("Estimate change", "We raise Q2 and FY net-revenue estimates modestly on better-than-expected "
                          "processing volume and a favorable mix shift toward integrated payments."),
      ("Margins", "Operating leverage is coming through; we nudge EBITDA higher and see a credible path to "
                  "mid-20s margins as the software mix builds."),
      ("Catalysts", "Q2 print, a potential guidance raise, and new ISV partner announcements.")]),
]


def dedupe_documents(cid="demo", doc_types=("model", "research_note")):
    """Remove exact-duplicate analyst-research documents (same firm + filename + doc_type), keeping the
    newest, so the Research Library never shows the same model twice. Scoped to model / research_note
    only (NOT email_attachment, which can be linked from Calendar events) and never deletes a document
    an inbox item points at via doc_id. Idempotent. Returns the number deleted."""
    from collections import defaultdict

    from core import documents, inbox_queue
    referenced = set()
    for cat in ("model", "research_note", "ndr_request", "conference_invite",
                "meeting_confirmation", "speak_to_management", "shareholder_inquiry"):
        for it in (inbox_queue.list_items_by_category(cat, client_id=cid) or []):
            if it.get("doc_id") is not None:
                referenced.add(it["doc_id"])

    groups = defaultdict(list)
    for d in documents.list_documents(client_id=cid):        # newest first
        if d.get("doc_type") in doc_types:
            groups[(d.get("firm"), d.get("filename"), d.get("doc_type"))].append(d["id"])
    deleted = 0
    for _key, ids in groups.items():
        for stale in ids[1:]:                                # ids[0] is newest — keep it
            if stale in referenced:
                continue
            documents.delete_document(stale, client_id=cid)
            deleted += 1
    return deleted


def seed_research_library(cid="demo"):
    from core import documents
    made = 0
    for firm, analyst, rating, pt, fname, headline, paras in _NOTES:
        if documents.list_documents(firm=firm, doc_type="research_note", client_id=cid):
            continue                      # already seeded — idempotent
        pdf = _note_pdf(firm, analyst, rating, pt, headline, paras)
        documents.save_document(contact=analyst, firm=firm, doc_type="research_note",
                                filename=fname, file_bytes=pdf, content_type="application/pdf",
                                source="ir_inbox", client_id=cid)
        made += 1
    return made


# Per-firm inbox metadata — the subject line and the `extracted` payload the research_note
# category carries into recurring-Q&A prep, and what lights up the loop-readiness "Research
# notes" stage. `key_kpi` is the analyst's headline expectation; `topics` seed recurring Q&A.
# Fictional analyst emails on the reserved example.com domain (never a real inbox).
_INBOX = {
    "Ashfield Research": ("Ellis Grant", "egrant@ashfield-research.example.com",
        "NLKP Q2 preview — net take-rate is the tell; reiterate Buy, $43 PT",
        {"rating": "Buy", "price_target": 43.0,
         "key_kpi": "Net take-rate ~47 bps expected (5th straight quarter of expansion; path to 50+ bps)",
         "topics": ["net take-rate expansion", "PayFac attach", "gross-to-net bridge", "prepaid float"]}),
    "Denby Securities": ("Marta Reyes", "mreyes@denby-sec.example.com",
        "NLKP initiation — Buy, $45 PT; durable net-revenue compounder",
        {"rating": "Buy", "price_target": 45.0,
         "topics": ["ISV moat", "PayFac-as-a-service", "valuation ~11x NTM net revenue"]}),
    "Westmark Partners": ("Owen Pike", "opike@westmark-partners.example.com",
        "NLKP — Hold into the print; want float-durability evidence",
        {"rating": "Hold", "price_target": 38.0,
         "topics": ["prepaid float durability", "conservative EBITDA", "gross-to-net bridge"]}),
    "Calder & Co.": ("Neil Barrow", "nbarrow@calder-co.example.com",
        "NLKP estimate update — raising on stronger volume; reiterate Buy, $42 PT",
        {"rating": "Buy", "price_target": 42.0,
         "topics": ["estimate raise", "operating leverage", "mid-20s margin path", "new ISV partners"]}),
}


def seed_research_inbox(cid="demo"):
    """Enqueue one research_note IR-inbox item per seeded research PDF, linked to its document via
    doc_id and marked reviewed/confirmed — so the loop-readiness 'Research notes' stage lights up and
    recurring-Q&A prep has real extracted content to pull, without cluttering the pending 'waiting on
    you' inbox. Idempotent: skips a firm that already has a research_note queue item. Returns the count
    enqueued."""
    from core import documents, inbox_queue
    existing = {it.get("firm") for it in (inbox_queue.list_items_by_category("research_note", client_id=cid) or [])}
    made = 0
    for firm, (analyst, email, subject, extracted) in _INBOX.items():
        if firm in existing:
            continue                      # already enqueued — idempotent
        docs = documents.list_documents(firm=firm, doc_type="research_note", client_id=cid)
        doc_id = docs[0]["id"] if docs else None
        fname = docs[0]["filename"] if docs else None
        item_id = inbox_queue.enqueue_item(
            "research_note", contact=analyst, firm=firm, subject=subject,
            extracted=extracted, doc_id=doc_id, filename=fname,
            source="ir_inbox", client_id=cid, sender_email=email)
        # Already filed to the Research Library — close it out so it counts toward readiness and
        # feeds Q&A prep without sitting in the pending "waiting on you" queue.
        inbox_queue.mark_confirmed(item_id, outcome="Filed to Research Library", client_id=cid)
        made += 1
    return made


if __name__ == "__main__":
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config.client_config import reload_registry, set_active_client_id
    reload_registry()
    set_active_client_id("demo")
    n = seed_research_library("demo")
    d = dedupe_documents("demo")
    q = seed_research_inbox("demo")
    print(f"Seeded {n} research note(s); removed {d} duplicate model/research doc(s); "
          f"enqueued {q} research_note inbox item(s).")
