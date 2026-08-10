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
     "Q2 preview: PayFac attach is inflecting; net-revenue take-rate should expand again. Reiterate Buy.",
     [("Thesis", "We continue to see Northlake as a net-revenue compounder mispriced on a gross-revenue "
                 "optic. PayFac attach is the swing factor — as more volume moves onto the integrated "
                 "acquiring stack, net take-rate steps up and the mix shifts toward durable, recurring "
                 "software-like economics."),
      ("Into the print", "We model Q2 net revenue of ~$25.9M and adj. EBITDA of ~$14M. Watch the gross-to-net "
                         "bridge and prepaid-float commentary — the two items the buy-side keeps flagging."),
      ("Risks", "Rate-sensitive prepaid float; concentration in a handful of ISV partners; competitive "
                "pricing on interchange-plus.")]),
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
                          "processing volume and a favorable mix shift toward integrated acquiring."),
      ("Margins", "Operating leverage is coming through; we nudge EBITDA higher and see a credible path to "
                  "mid-20s margins as the software mix builds."),
      ("Catalysts", "Q2 print, a potential guidance raise, and new ISV partner announcements.")]),
]


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


if __name__ == "__main__":
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config.client_config import reload_registry, set_active_client_id
    reload_registry()
    set_active_client_id("demo")
    n = seed_research_library("demo")
    print(f"Seeded {n} research note(s) into the demo Research Library.")
