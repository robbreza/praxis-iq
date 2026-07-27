# Sterne Agee NDR itinerary — OCR + ingest (Jul 2026)

Recovered buy-side contacts from a **scanned** 2014/15 Sterne Agee software non-deal-roadshow
itinerary (`E:\HPSCANS\stern.pdf`, analyst R. Breza). The scan has no text layer, so it was OCR'd.

## Pipeline
- **`ocr_stern.py`** — rasterizes each PDF page with PyMuPDF and runs Tesseract OCR (see the file
  header for the one-time Windows install: `winget install UB-Mannheim.TesseractOCR` + `pip install
  pytesseract pymupdf pillow`). 6 pages, clean extraction of the structured itinerary
  (time / city / Account / Address / Contact + Tel / Sales).
- **`ingest_stern.py`** — ingests only the STILL-LIVE accounts with their itinerary contact + direct
  phone. Contacts are VINTAGE (US leg May 2014, UK leg Jan 2015): the firm is live but the person may
  have moved, so each is `validation_status='stale'`, low confidence, with a "verify before outreach"
  provenance note. UK leg tagged `country=UK`. Firms updated to current names where merged/rebranded.

## Live firms ingested (17 contacts, 13 firms)
- **US:** Falcon Point Capital · Columbia Threadneedle (Menlo Park + Portland) · PIMCO · Nicholas Investment Partners
- **UK (the "good international accounts"):** Janus Henderson (Edinburgh) · Aviva Investors · AXA Investment
  Managers (Framlington) · BlackRock UK · Polar Capital · M&G Investments · USS Investment Management
  (pension) · Lansdowne Partners · Columbia Threadneedle (London) · Ninety One

## Skipped (dead / merged-away / unconfirmable — cross-checked vs the target-list verifications)
PresPoint, QCM, Montibus, Archon, Wall Street Associates, GROW (unconfirmable/likely defunct);
RS Investment Mgmt → Victory Capital; Rainier → Manning & Napier; Relational Investors (wound down);
Alliance Trust Investments → Liontrust; Henderson/Threadneedle/Investec updated to current names above.

## Notes
- The direct phones age better than the names — good for reconnecting even where the person moved
  (e.g. William de Gale left BlackRock UK to found BlueBox AM; flagged in the record).
- Tesseract accuracy on this scan was high for typed text; the last page's handwriting OCR'd as noise
  and was ignored.
