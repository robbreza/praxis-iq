"""
scripts/seed_earnings_demo.py — populate the illustrative demo's Earnings Cycle so every tab tells a
coherent story. Fictional issuer NLKP (Northlake Payments); illustrative only. Idempotent.

Seeds three things:
  1. earnings_surprise_log.json — NLKP's beat/miss track record (Consensus Tracker tab). Without it the
     tab falls back to a hardcoded USIO default (wrong data for the demo).
  2. The Q1 2026 call transcript (Call Transcripts tab) with its AI-summary fields written directly —
     deterministic, no LLM call. The full_text is assembled from speaker/body turns with timestamps at a
     realistic ~130 wpm, in the vendor format core/morning_after.py parses, so the Morning After tab's
     section-timing works off the tape (not an estimate). Only Q1 is ingested — the Q2 call hasn't
     happened (it lives in Script Generation as a draft), so any Q2 "transcript" stub is deleted.
  3. (The Prior Qtr Review lookback reads #1 + the Q1 transcript's summary via an illustrative branch in
     earnings_page.py.)

Run: python scripts/seed_earnings_demo.py   ·   or import seed_earnings_demo(cid) from the main seed.
"""
import json

# ── 1. Surprise / beat-miss history — schema mirrors earnings_page._default_surprises() ──────────────
_SURPRISES = [
    {"quarter": "Q3 2025", "date": "2025-11-06", "rev_actual": 23.2, "rev_consensus": 22.7,
     "rev_whisper": 23.0, "eps_actual": 0.08, "eps_consensus": 0.06, "ah_move": 0.041,
     "implied_move": 0.060, "3day_move": 0.038, "sector_3day": 0.005, "stock_pre_close": 27.10,
     "guidance_vs_embedded": "In-line", "pt_changes": 1, "pt_change_avg": 1.00,
     "notes": "Solid quarter; PayFac attach +21%. Prepaid float stable. Guide reiterated — market wanted "
              "a raise and didn't get one, so a modest AH pop only.",
     "pre_empt_score": 7, "call_score": 58},
    {"quarter": "Q4 2025", "date": "2026-02-19", "rev_actual": 24.6, "rev_consensus": 24.1,
     "rev_whisper": 24.4, "eps_actual": 0.10, "eps_consensus": 0.09, "ah_move": 0.028,
     "implied_move": 0.055, "3day_move": 0.031, "sector_3day": -0.004, "stock_pre_close": 29.40,
     "guidance_vs_embedded": "Above", "pt_changes": 2, "pt_change_avg": 1.50,
     "notes": "Clean beat and an above-consensus FY26 initial guide. Take-rate expansion the story; two "
              "PT raises. Prepaid-float durability the lone pushback in Q&A.",
     "pre_empt_score": 8, "call_score": 63},
    {"quarter": "Q1 2026", "date": "2026-05-13", "rev_actual": 25.3, "rev_consensus": 24.4,
     "rev_whisper": 24.9, "eps_actual": 0.12, "eps_consensus": 0.09, "ah_move": 0.086,
     "implied_move": 0.060, "3day_move": 0.072, "sector_3day": 0.010, "stock_pre_close": 30.20,
     "guidance_vs_embedded": "Above", "pt_changes": 3, "pt_change_avg": 2.00,
     "notes": "Record Q1 — PayFac attach +28% drove the beat and net take-rate stepped up again. Prepaid "
              "float held despite the rate backdrop. Reiterated FY guide with an explicit upside bias into "
              "H2; three PT raises the next morning.",
     "pre_empt_score": 8, "call_score": 66},
]

# ── 2. Call transcript ───────────────────────────────────────────────────────────────────────────────
# Stored as (speaker, body) turns; _assemble() stamps each with an HH:MM:SS timestamp derived from the
# body's word count at ~130 wpm (operator turns get a short fixed duration), so the Morning After tab's
# section timing AND its wpm readout are internally consistent and realistic. The header format
# ("Speaker, Role\nHH:MM:SS\nbody") is exactly what core/morning_after.py's _TURN regex matches.
_WPM = 130

_Q1_TURNS = [
    ("Operator",
     "Good afternoon, and welcome to Northlake Payments' first quarter fiscal 2026 earnings conference "
     "call. All participants will be in a listen-only mode. After today's presentation, there will be an "
     "opportunity to ask questions. Please note this event is being recorded. I would now like to turn the "
     "conference over to Dana Whitfield, Director of Investor Relations. Please go ahead."),

    ("Dana Whitfield, Investor Relations",
     "Thank you, operator, and good afternoon, everyone. Welcome to Northlake Payments' first quarter 2026 "
     "earnings call. With me today are Marcus Ellery, our Chief Executive Officer, and Priya Raman, our "
     "Chief Financial Officer. Marcus will begin with a review of the quarter and our strategy, Priya will "
     "walk through the financial results and our outlook, and then we'll open the line for your questions. "
     "Before we begin, I'd like to remind everyone that today's call contains forward-looking statements "
     "within the meaning of the Private Securities Litigation Reform Act. These statements are subject to "
     "risks and uncertainties that could cause actual results to differ materially, and we refer you to the "
     "risk factors in our most recent SEC filings. We will also discuss certain non-GAAP financial "
     "measures; a reconciliation to the most comparable GAAP measures is available in today's press "
     "release, which is posted to the investor relations section of our website. With that, I'll turn the "
     "call over to Marcus."),

    ("Marcus Ellery, Chief Executive Officer",
     "Thank you, Dana, and good afternoon, everyone. Thank you all for joining us. The first quarter was a "
     "record for Northlake across the metrics that matter most to this business. Total revenue of $25.3 "
     "million grew 19% year over year and came in above the high end of the guidance range we gave you in "
     "February. Adjusted EPS was $0.12, up from $0.03 in the prior-year quarter. But as I told our team the "
     "morning the quarter closed, the number I care most about is not the revenue line — it's the mix. "
     "Integrated payments volume grew 28% year over year, and as that mix continues to build, our net "
     "take-rate steps up. We are converting software partners into full payments relationships faster than "
     "we modeled at the start of the year, and that is the single most important trend in our story. "
     "Let me put the quarter in context, because I think the transformation of this company is still "
     "underappreciated. Two years ago, Northlake was, for all practical purposes, a payment processor "
     "competing on price. We moved transactions, we charged a spread, and we lived and died on volume. "
     "Today we are an embedded-payments platform for vertical software companies. When one of our ISV "
     "partners — a practice-management system, a field-services platform, a nonprofit CRM — turns on "
     "integrated payments, we don't simply process a transaction. We become the payments infrastructure "
     "inside their product. We own the acquiring relationship, we manage the underwriting and risk, and we "
     "keep the net spread. That is a structurally better business than the one we ran two years ago, and "
     "the first quarter is the clearest evidence yet that the strategy is compounding. "
     "I'll walk you through the three drivers of the quarter. The first is PayFac attach, which is the core "
     "of everything we do. New-partner onboarding accelerated — we brought on a record number of new "
     "integrated partners in the quarter — and just as importantly, attach among our existing partners "
     "improved as those partners matured on the platform. This is the flywheel we've described: a partner "
     "integrates, their merchants adopt payments, adoption deepens over the following quarters, and our "
     "revenue per partner climbs without us adding a single new logo. The installed base is doing more of "
     "the work every quarter. The second driver is retention. Net revenue retention was above 110% for the "
     "fourth consecutive quarter. In this business, retention is destiny — the cost to acquire a partner is "
     "real, and the return on that acquisition is entirely a function of how long they stay and how much "
     "they grow. Above-110% net retention means our existing book is expanding faster than any churn, and "
     "our churn stays low because, frankly, once payments are embedded in a partner's workflow, we are very "
     "difficult to remove. The third driver is discipline. We delivered this record quarter while expanding "
     "margins, which Priya will detail in a moment. We are not buying growth, we are not subsidizing "
     "merchants to inflate a headline, and we are not chasing gross volume for its own sake. Every dollar of "
     "revenue growth this quarter carried incremental margin, because the attach motion has software-like "
     "economics. "
     "Before I hand it to Priya, a word on where we go from here. Our strategy has not changed and it will "
     "not change: we are focused on the attach motion, because that is where durable, recurring economics "
     "live. We will keep investing in partner onboarding and in the platform capabilities that make us the "
     "easiest payments provider to turn on and the hardest to turn off. We see a long runway in our "
     "existing verticals and a real opportunity in adjacent ones, and the pipeline of ISV partners we're in "
     "conversations with is the strongest it has been in the company's history. I am more confident in this "
     "model today than at any point since we began the transformation. "
     "Let me give you a little more color by vertical, because the strength was broad-based. In healthcare "
     "practice management, our largest vertical, integrated volume grew in the low thirties as more clinics "
     "turned on card-present and card-not-present acceptance directly through their scheduling workflow. "
     "Field services — the HVAC, plumbing, and pest-control platforms — was our fastest-growing vertical, up "
     "in the high thirties, as those partners increasingly bundle payments into the technician's mobile app "
     "at the point of service. And in the nonprofit and faith-based vertical, where donation flows are the "
     "use case, we saw strong seasonal volume and, importantly, rising recurring-gift adoption, which is "
     "exactly the kind of sticky, predictable volume we want. And I'd note that no single partner represents "
     "more than a low-single-digit percentage of revenue, so this is a diversified book, not a concentration "
     "story. "
     "I also want to underscore the size of the runway, because I think it's the most important thing for "
     "investors to understand. Across our existing partners, the majority of their end merchants have not "
     "yet adopted integrated payments. That is the opportunity directly in front of us — we don't need to "
     "win the whole market, we need to keep converting the merchants already sitting inside our partners' "
     "software. And beyond that installed base, the adjacent verticals we're evaluating roughly double our "
     "addressable partner universe over time. So when I talk about a long runway, I mean years of attach "
     "growth from assets we already have, with real optionality layered on top. "
     "With that, I'll turn it over to "
     "Priya to walk through the financials and our outlook."),

    ("Priya Raman, Chief Financial Officer",
     "Thank you, Marcus, and good afternoon, everyone. I'll cover the first-quarter results and then our "
     "outlook. First-quarter net revenue was $25.3 million, up 19% year over year and above the high end of "
     "our $24.6 to $25.0 million guidance range. The growth was led by integrated payments, where volume "
     "grew 28% and net revenue grew faster than volume as take-rate expanded. Our transaction-based revenue "
     "grew in the mid-single digits, consistent with our expectation that the legacy processing book grows "
     "slowly while the integrated book compounds. Adjusted EPS was $0.12, ahead of the $0.09 consensus and "
     "up from $0.03 a year ago. "
     "Turning to margins. Gross profit margin expanded 180 basis points year over year, to the high-fifties, "
     "as the revenue mix shifted toward integrated acquiring, which carries a structurally higher margin "
     "than our legacy processing. Adjusted EBITDA was $5.1 million, a margin of roughly 20%, up more than "
     "300 basis points year over year, as we held operating expense growth well below revenue growth. And we "
     "generated positive free cash flow in the quarter, which funds the partner-onboarding investment Marcus "
     "described without drawing on the balance sheet. We ended the quarter with $41 million in cash and no "
     "debt. "
     "Let me address prepaid float directly, because I know it's a topic for several of you. Float balances "
     "were stable in the quarter despite the rate environment, and the contribution to revenue was "
     "consistent with prior quarters. To be very clear: we do not model float as a growth driver, it is a "
     "small and stable contributor to the P&L, and the growth in this business is the attach motion, full "
     "stop. If rates normalize from here, the sensitivity to our model is modest and well within the range "
     "we plan for. "
     "Now to guidance. For the second quarter, we expect net revenue of $25.6 to $26.0 million. For the "
     "full year, we are reiterating our guidance of $103 to $105 million in net revenue and adjusted EBITDA "
     "margin of approximately 20%. Given the first-quarter trajectory, we see the bias to the upside on the "
     "full-year range, and we expect the second half to be stronger than the first as new-partner go-lives "
     "weight toward the back half. We are not raising the formal range today — it is early in the year — but "
     "I want to be direct that the momentum we are seeing supports the high end. "
     "Let me give you a little more detail on the model to help with your estimates. Of the $25.3 million in "
     "net revenue, integrated payments now represents just over sixty percent of the total, up from about "
     "fifty percent a year ago, and that mix shift is the single biggest driver of the take-rate expansion "
     "you're seeing. Our blended net take-rate expanded several basis points year over year, and to be "
     "clear, that came entirely from mix — we did not raise pricing. On the expense side, we grew operating "
     "expenses in the high single digits against 19% revenue growth, which is where the operating leverage "
     "comes from; we continue to invest in partner onboarding and engineering, but those investments scale "
     "sublinearly with revenue. Days sales outstanding was stable, we have no debt, and the $41 million of "
     "cash gives us ample flexibility to fund the onboarding investment internally. "
     "A couple of assumptions embedded in our guidance, since I know you'll ask. We assume no change in the "
     "rate environment and no contribution from float growth. We assume the back-half-weighted go-live "
     "cadence Marcus described, which is why we expect the second half to be stronger than the first. And we "
     "assume continued mid-single-digit growth in the legacy processing book, with the integrated book "
     "carrying the story. If the go-lives land as we expect, that is where the upside bias on the full-year "
     "range comes from. "
     "With that, operator, we are "
     "ready to open the call for questions."),

    ("Operator",
     "Thank you. We will now begin the question-and-answer session. Our first question comes from Ellis "
     "Grant with Ashfield Research. Please go ahead."),

    ("Ellis Grant, Ashfield Research",
     "Good afternoon, and congratulations on the quarter. Marcus, can you frame the sustainability of the "
     "PayFac attach rate? Is the 28% a new baseline we should carry forward, or is there an element of "
     "pull-forward in the number we should be aware of?"),

    ("Marcus Ellery, Chief Executive Officer",
     "Thanks, Ellis. We see it as structural, not a pull-forward. There are two things supporting it. "
     "First, the pipeline of new ISV partners is strong, so new-logo attach continues. But second, and more "
     "importantly, attach improves as each existing partner matures on the platform — their merchants keep "
     "adopting payments over the quarters following integration. So even if we brought on zero new partners, "
     "the installed base would keep contributing attach growth. That's the durability. We'd rather "
     "under-promise on the exact percentage, because it will move quarter to quarter, but the trend line is "
     "real and we expect it to persist."),

    ("Ellis Grant, Ashfield Research",
     "That's helpful. And a follow-up for Priya — can you give us the gross-to-net revenue bridge versus the "
     "net-revenue peers? It's the piece the buy-side keeps asking us about."),

    ("Priya Raman, Chief Financial Officer",
     "Fair question, and we're going to put a clean bridge in the deck this quarter so it's easy to follow. "
     "The short version is this: benchmark us on gross profit, not gross revenue — that's where the model's "
     "economics show up. Because we report net revenue rather than gross, a simple revenue-multiple "
     "comparison to the gross-revenue names understates us. On a gross-profit basis, we compare very "
     "favorably to the net-revenue peers you're thinking of, and the bridge we'll publish walks from our "
     "reported net revenue to gross profit so you can line us up apples-to-apples. I think it will make the "
     "comparison obvious."),

    ("Operator",
     "The next question comes from Owen Pike with Westmark Partners. Please go ahead."),

    ("Owen Pike, Westmark Partners",
     "Thanks for taking my question. Priya, staying on prepaid float — if rates normalize from here, how "
     "much is actually at risk to the model, and how should we think about it in our estimates?"),

    ("Priya Raman, Chief Financial Officer",
     "It's limited, Owen. Float is a small and stable contributor and we don't guide to it. If rates move a "
     "hundred basis points, the impact to full-year revenue is modest — low single-digit millions at the "
     "extreme — and it's well within the range we plan for in our guidance. I'd encourage you not to model "
     "float as a swing factor, because in our P&L it isn't one. The growth story is attach, and attach is "
     "not rate-sensitive."),

    ("Operator",
     "The next question comes from Marta Reyes with Denby Securities. Please go ahead."),

    ("Marta Reyes, Denby Securities",
     "Congrats on the print. Marcus, on capital allocation — with free cash flow turning positive, how are "
     "you thinking about reinvestment versus returning capital, and does M&A factor in at all?"),

    ("Marcus Ellery, Chief Executive Officer",
     "Right now the highest-return use of our capital is investing in partner onboarding and in the "
     "platform, because the attach motion compounds — a dollar we put into bringing on and ramping partners "
     "returns for years. So that's the priority. We'll be disciplined; we have no plans to chase M&A for "
     "scale, and we're not interested in buying revenue that doesn't fit the attach model. If we generate "
     "cash beyond what the organic opportunity can absorb, we'll evaluate returning it to shareholders, but "
     "we're not there yet, and the bar for any alternative use is the return we get on the attach motion."),

    ("Operator",
     "The next question comes from Neil Barrow with Calder and Company. Please go ahead."),

    ("Neil Barrow, Calder & Co.",
     "Thanks. Can you size the ISV pipeline heading into the second half, and help us understand the cadence "
     "of new-partner go-lives — is it linear, or should we expect it back-half weighted?"),

    ("Priya Raman, Chief Financial Officer",
     "The pipeline is the strongest it's been, and I'd point you to the back half for the cadence. We won't "
     "give a specific partner-count number, but go-lives tend to be back-half weighted because partners "
     "take a quarter or two to finish integration and testing before they turn on. That timing is a big part "
     "of why we're pointing to a stronger second half and why we see the bias to the upside on the full-year "
     "range. As those partners go live, they contribute attach growth into next year as well."),

    ("Operator",
     "The next question comes from Sara Lindqvist with Brightwater Equity. Please go ahead."),

    ("Sara Lindqvist, Brightwater Equity",
     "Thank you. A bigger-picture question for Marcus — what is the competitive moat here? What stops a "
     "larger processor from replicating the attach motion with your partners?"),

    ("Marcus Ellery, Chief Executive Officer",
     "It's integration depth and switching cost, Sara. Once payments are embedded in a partner's software "
     "workflow — the way funds move, the way reconciliation works, the way their merchants get onboarded — "
     "ripping that out is painful and risky for the partner, and it puts their own merchant relationships at "
     "risk. We win by being the easiest to turn on and the least likely to be turned off. A larger "
     "processor can match us on price, but price isn't what keeps a partner; the embedded workflow and the "
     "trust that we'll manage the risk correctly is what keeps them. Scale doesn't replicate that — depth of "
     "integration and years of a working relationship do."),

    ("Operator",
     "The next question comes from Tom Castellano with Meridian Capital Markets. Please go ahead."),

    ("Tom Castellano, Meridian Capital Markets",
     "Thanks. Priya, on the margin trajectory — you did roughly 20% adjusted EBITDA margin this quarter. "
     "How should we think about the path from here, and where can this model get to at scale?"),

    ("Priya Raman, Chief Financial Officer",
     "It's a good question, Tom. The margin expansion is a direct function of the mix shift, so as "
     "integrated becomes a larger share of the book, the blended margin structurally improves. I'm not going "
     "to put a specific long-term target on the record today, but I'd frame it this way: the integrated "
     "business carries software-like gross margins, our operating expenses scale sublinearly with revenue, "
     "and we generate cash. So the direction is clearly up, and I'd think of 20% as a milestone on the way, "
     "not a ceiling. As the second-half go-lives ramp and the mix continues to shift, you should expect "
     "continued margin expansion, and over a multi-year horizon we believe there is meaningful room above "
     "where we are today. What we won't do is sacrifice the onboarding investment to hit a near-term margin "
     "number, because that investment is what compounds the attach motion."),

    ("Operator",
     "The next question comes from Rachel Kim with Harborview Securities. Please go ahead."),

    ("Rachel Kim, Harborview Securities",
     "Thank you. Marcus, you mentioned adjacent verticals a couple of times. Can you be more specific about "
     "which adjacencies you're evaluating and the timing of any expansion?"),

    ("Marcus Ellery, Chief Executive Officer",
     "I'll be a little careful here for competitive reasons, Rachel, but I can give you the framework. We "
     "look for verticals with three characteristics: fragmented software providers who need a payments "
     "partner rather than building it themselves, recurring or high-frequency payment flows, and merchants "
     "who are underserved by the large processors. Healthcare, field services, and nonprofit all fit that "
     "profile, and there are several adjacent categories — property management, membership and recreation, "
     "and education administration — that share the same DNA. Our approach is to enter a new vertical "
     "through a small number of anchor ISV partners, prove the model, and then expand from there. We're "
     "deliberate about it; we would rather go deep in a few verticals than shallow across many. On timing, I "
     "would think of adjacency expansion as a multi-year driver layered on top of the attach growth in our "
     "existing verticals, not a this-year event. The near-term story, and the one I want you focused on, is "
     "the installed base we already have."),

    ("Operator",
     "The next question comes from David Osei with Pinnacle Research. Please go ahead."),

    ("David Osei, Pinnacle Research",
     "Thanks for taking my question. Two related ones — how sensitive is your volume to consumer spending if "
     "the macro softens, and what are you seeing on churn?"),

    ("Marcus Ellery, Chief Executive Officer",
     "On the macro, our volume is tied to our partners' merchants, and those merchants skew toward "
     "non-discretionary and recurring categories — a clinic visit, a service call, a recurring donation — so "
     "we're structurally less exposed to discretionary consumer swings than a processor concentrated in "
     "retail or travel. We're not immune to a broad downturn, but the mix is defensive by design. On churn, "
     "it remains low and was stable in the quarter. The reason is the one I gave earlier: once we're "
     "embedded in a partner's workflow, we are hard to remove, and partner-level retention is what matters "
     "most because a single partner brings a whole book of merchants. We watch merchant-level attrition too, "
     "and it's running in line with our expectations. Priya, do you want to add anything on the numbers?"),

    ("Priya Raman, Chief Financial Officer",
     "Just that net revenue retention above 110% already nets out whatever churn we see, so that headline "
     "retention number is the cleanest single way to see it. Churn is not a concern in the model today, and "
     "it's not an assumption we're relying on in the guidance."),

    ("Operator",
     "The next question comes from James Meridian with Cascade Securities. Please go ahead."),

    ("James Meridian, Cascade Securities",
     "Thanks. Priya, the second-quarter guide of $25.6 to $26.0 million implies fairly modest sequential "
     "growth off a record first quarter. Is that conservatism, seasonality, or something in the business we "
     "should understand?"),

    ("Priya Raman, Chief Financial Officer",
     "It's primarily the go-live cadence, James, plus a degree of conservatism this early in the year. As I "
     "mentioned, new-partner go-lives are back-half weighted — partners finish integration and turn on later "
     "in the year — so the sequential step-up is more pronounced in the third and fourth quarters than from "
     "the first to the second. There's also a modest seasonal element in a couple of our verticals. So I "
     "wouldn't read the second-quarter sequential as any change in trajectory; the full-year range, and the "
     "upside bias we've talked about, are the better way to think about the shape of the year. We would "
     "rather guide the quarter prudently and let the full year carry the story."),

    ("Operator",
     "The next question comes from Laura Benson with Summit Equity Research. Please go ahead."),

    ("Laura Benson, Summit Equity Research",
     "Thank you. Can you help us understand the unit economics — how should we think about the lifetime "
     "value of a partner relative to what it costs you to acquire and onboard one?"),

    ("Marcus Ellery, Chief Executive Officer",
     "It's the right question to anchor on, Laura, because it's exactly how we think internally. Without "
     "giving you the specific figures, the shape is very attractive. The cost to acquire and onboard a "
     "partner is largely one-time, and the revenue from that partner compounds for years as their merchants "
     "adopt payments and as new merchants join their platform. So the payback period is well inside a couple "
     "of years for a typical partner, the lifetime value is a large multiple of the acquisition cost, and "
     "that multiple improves over time because attach keeps deepening. That is the whole basis for "
     "prioritizing onboarding investment over near-term margin — the return on that investment is the best "
     "use of our capital, and it's why net revenue retention above 110% matters so much. A partner we "
     "brought on two years ago is generating meaningfully more revenue today than it did in its first "
     "quarter with us, and it's costing us almost nothing incremental to keep."),

    ("Operator",
     "We have a follow-up from Ellis Grant with Ashfield Research. Please go ahead."),

    ("Ellis Grant, Ashfield Research",
     "Thanks for squeezing me back in. Just quickly — with three price-target raises since the print, does "
     "the sell-side reaction change how you're thinking about communicating the model, particularly that "
     "gross-to-net bridge?"),

    ("Priya Raman, Chief Financial Officer",
     "It reinforces the priority, Ellis. The bridge is the clearest way to close the gap between how we "
     "report, on net revenue, and how the gross-revenue names report, and we've committed to putting it in "
     "the deck this quarter. We would rather the Street value us correctly on gross profit than have a "
     "reporting convention obscure the economics of the business. So clearer disclosure on that bridge is a "
     "near-term focus, and you will see it from us this quarter."),

    ("Operator",
     "This concludes our question-and-answer session. I would like to turn the conference back over to "
     "Marcus Ellery for any closing remarks."),

    ("Marcus Ellery, Chief Executive Officer",
     "Thank you all for joining us today. The first quarter was a record, the attach strategy is clearly "
     "working, and we are carrying real momentum into the second half of the year. Thank you to our team and "
     "to our partners for the quarter, and thank you to our shareholders for your continued support. We look "
     "forward to updating you on our second quarter. Have a good evening."),

    ("Operator",
     "The conference has now concluded. Thank you for attending today's presentation. You may now disconnect."),
]


def _assemble(turns, wpm=_WPM):
    """Join (speaker, body) turns into the vendor transcript format morning_after parses, stamping each
    turn with an HH:MM:SS timestamp so the elapsed time matches the body length at ~`wpm` (operator
    turns get a short fixed duration). Deterministic — same input, same tape."""
    lines, t = [], 0
    for spk, body in turns:
        lines.append(f"{spk}\n{t//3600:02d}:{(t % 3600)//60:02d}:{t % 60:02d}\n{body}")
        if spk.startswith("Operator"):
            dur = 60 if t == 0 else 18          # intro runs longer; transitions are brief
        else:
            dur = max(20, round(len(body.split()) / wpm * 60))
        t += dur
    return "\n\n".join(lines)


_TRANSCRIPTS = {
    "Q1 2026": {
        "call_date": "2026-05-13",
        "full_text": _assemble(_Q1_TURNS),
        "ai_summary": ("Record Q1: net revenue $25.3M (+19% YoY, above the high end of guidance) and adj. "
                       "EPS $0.12 vs $0.09 consensus. The beat was driven by PayFac attach (integrated "
                       "volume +28%) lifting net take-rate, with 180 bps of gross-margin expansion and "
                       "adjusted EBITDA margin near 20%. Management framed attach as structural, not a "
                       "pull-forward, guided Q2 net revenue to $25.6–26.0M, reiterated the $103–105M FY "
                       "range with an explicit upside bias into H2, and pushed back on prepaid-float "
                       "concerns (stable balances, not modeled as a growth driver)."),
        "key_quotes": [
            {"quote": "Integrated payments volume grew 28%, and as that mix continues to build, our net take-rate steps up.",
             "speaker": "Marcus Ellery, CEO"},
            {"quote": "We are reiterating our guidance and, given the first-quarter trajectory, we see the bias to the upside on the full-year range.",
             "speaker": "Priya Raman, CFO"},
            {"quote": "Benchmark us on gross profit, not gross revenue — that's where the model's economics show up.",
             "speaker": "Priya Raman, CFO"},
        ],
        "guidance_language": [
            "Q2 net revenue guided to $25.6–26.0M.",
            "Reiterated full-year FY2026 net revenue of $103–105M and ~20% adj. EBITDA margin.",
            "Explicit upside bias to the full-year range; second half expected stronger than the first.",
            "Do not model prepaid float as a growth driver — modest, well-planned rate sensitivity.",
        ],
        "qa_risk_topics": [
            {"severity": "MEDIUM", "topic": "PayFac attach sustainability",
             "why": "Analysts pressed whether 28% attach growth is a durable baseline or a pull-forward."},
            {"severity": "MEDIUM", "topic": "Gross-to-net revenue bridge",
             "why": "Repeated ask for a clean bridge vs net-revenue peers — commitment made to add it to the deck."},
            {"severity": "LOW", "topic": "Prepaid float rate sensitivity",
             "why": "Recurring concern on float durability if rates normalize; management framed exposure as limited."},
        ],
    },
}
_STALE_TRANSCRIPTS = ["Q2 2026"]   # a future call has no transcript — remove any seeded stub


def seed_surprise_log(cid="demo"):
    from core import db
    db.save_json("earnings_surprise_log.json", _SURPRISES, client_id=cid)
    return len(_SURPRISES)


def _write_summary(cid, quarter, rec):
    """Write the AI-summary fields directly (deterministic; no LLM), mirroring the UPDATE in
    transcripts.summarize_transcript."""
    if rec.get("ai_summary") is None:
        return
    from core import db
    conn = db.get_connection()
    pg = db.connection_is_postgres(conn)
    try:
        cur = conn.cursor()
        if pg:
            from psycopg2.extras import Json
            cur.execute(
                "UPDATE call_transcripts SET ai_summary=%s, key_quotes=%s, qa_risk_topics=%s, "
                "guidance_language=%s, summarized_at=now() WHERE client_id=%s AND quarter=%s",
                (rec["ai_summary"], Json(rec["key_quotes"]), Json(rec["qa_risk_topics"]),
                 Json(rec["guidance_language"]), cid, quarter))
        else:
            import datetime as _dt
            cur.execute(
                "UPDATE call_transcripts SET ai_summary=?, key_quotes=?, qa_risk_topics=?, "
                "guidance_language=?, summarized_at=? WHERE client_id=? AND quarter=?",
                (rec["ai_summary"], json.dumps(rec["key_quotes"]), json.dumps(rec["qa_risk_topics"]),
                 json.dumps(rec["guidance_language"]), _dt.datetime.now().isoformat(), cid, quarter))
        conn.commit()
    finally:
        conn.close()


def seed_transcripts(cid="demo"):
    from core import transcripts
    for quarter in _STALE_TRANSCRIPTS:                 # a future call has no transcript
        try:
            transcripts.delete_transcript(quarter, client_id=cid)
        except Exception:
            pass
    for quarter, rec in _TRANSCRIPTS.items():
        transcripts.ingest_transcript(rec["full_text"], quarter, call_date=rec["call_date"],
                                      source="illustrative-demo", client_id=cid)
        _write_summary(cid, quarter, rec)
    return len(_TRANSCRIPTS)


# ── 3. Script workflow — the Q2 2026 script, mid-flight. q2_numbers are DEVELOPED from the Q1 2026
# transcript (net rev $25.3M, integrated +28%, NRR 112%, take-rate ~46bps, ~20% EBITDA margin) and
# carried forward to Q2 actuals; the three Street KPIs the CFO enters are Integrated Volume (TPV) + YoY,
# Net Revenue Retention, and Net Take-Rate. Persona scripts read at Northlake's scale, not USIO's.
_Q2_NUMBERS = {
    "rev": 25.9, "integrated": 16.1, "legacy": 9.8,
    "gp": 15.1, "gm": 58.3, "ebitda": 5.4, "eps": 0.13, "sga": 9.7,
    "tpv": 3.42, "tpv_yoy": 27.0, "nrr": 112.0, "take_rate": 47.0, "cash": 44.0,
    # Prior quarter (Q1 2026), from the transcript — the baseline the input is carried forward from.
    "prior": {"rev": 25.3, "eps": 0.12, "gm": 57.5, "ebitda": 5.1, "integrated_mix": 60.0,
              "tpv": 3.29, "tpv_yoy": 28.0, "nrr": 112.0, "take_rate": 46.0},
    "what_new": ("Q2 net revenue of $25.9M beat the $25.6–26.0M guide. Integrated payments led again — "
                 "TPV +27% YoY and 62% of net revenue. Net take-rate expanded to 47 bps and net revenue "
                 "retention held above 110%. Adj. EBITDA of $5.4M, ~21% margin. We're raising the FY range "
                 "to $104–106M and, as promised on the Q1 call, the gross-to-net bridge is in the deck."),
    "submitted_by": "Priya Raman (CFO)",
}

_SCRIPT_TEXT = {
    "ir_open": (
        "Good afternoon, and thank you for joining Northlake Payments' second quarter fiscal 2026 earnings "
        "call. I'm Dana Whitfield, Director of Investor Relations. With me are Marcus Ellery, Chief "
        "Executive Officer, and Priya Raman, Chief Financial Officer. Before we begin, today's call "
        "contains forward-looking statements subject to risks and uncertainties; please refer to the risk "
        "factors in our most recent SEC filings. We'll also reference non-GAAP measures, reconciled in "
        "today's release. With that, I'll turn the call over to Marcus."),
    "cfo_fin": (
        "Turning to the financials. Second-quarter net revenue was $25.9 million, up 18% year over year and "
        "above the high end of our $25.6 to $26.0 million guidance. Integrated payments led the quarter and "
        "now represents 62% of net revenue, up from 60% last quarter, which drove net take-rate to 47 basis "
        "points from 46. Gross margin expanded to 58.3%, adjusted EBITDA was $5.4 million — a margin of "
        "roughly 21% — and adjusted EPS was $0.13. Net revenue retention held above 110%, and we ended the "
        "quarter with $44 million in cash and no debt. As we promised on the first-quarter call, today's "
        "deck includes the gross-to-net revenue bridge. For the third quarter we expect net revenue of "
        "$26.4 to $26.9 million, and for the full year we are raising our guidance to $104 to $106 million, "
        "reflecting first-half momentum and the back-half-weighted go-live cadence."),
    "cro_ops": (
        "On the operational metrics the Street tracks. Integrated payments volume — our TPV — was $3.42 "
        "billion in the quarter, up 27% year over year, as new-partner go-lives and rising attach across "
        "the installed base both contributed. Net revenue retention was 112%, our fifth consecutive quarter "
        "above 110%, which reflects how durable the partner book is once payments are embedded. And net "
        "take-rate expanded to 47 basis points, entirely from the mix shift toward integrated acquiring — "
        "we did not change pricing. Partner onboarding accelerated again this quarter, and our ISV pipeline "
        "into the second half is the strongest it has been."),
    "ceo_narrative": (
        "Northlake delivered another record quarter, and more importantly the strategy continues to "
        "compound. The story is unchanged and it is working: as our software partners turn on integrated "
        "payments and their merchants adopt, our net take-rate steps up and the economics become more "
        "software-like. This quarter integrated payments reached 62% of net revenue, net revenue retention "
        "stayed above 110%, and TPV grew 27%. We are converting the installed base and adding new partners "
        "at the strongest pace in the company's history. Given that first-half trajectory, we are raising "
        "the full-year range to $104 to $106 million, and we continue to expect the second half to be "
        "stronger than the first as new-partner go-lives ramp. We remain focused on the attach motion, "
        "because that is where durable, recurring economics live, and we have years of runway from the "
        "merchants already sitting inside our partners' software."),
}

_ADVERSARIAL_QA = [
    "Integrated is now 62% of net revenue and TPV grew 27% — is that attach durable, or are you pulling "
    "forward adoption from the installed base?",
    "You delivered the gross-to-net bridge this quarter — does it change how the Street should value "
    "Northlake versus the net-revenue peers?",
    "Net take-rate expanded to 47 basis points on mix — how much take-rate expansion is left as integrated "
    "approaches 70–80% of revenue?",
    "You raised the full-year guide — how much is the first-half beat versus genuine second-half confidence "
    "in the go-live cadence?",
    "Net revenue retention has held around 112% for five quarters — what would cause it to step down, and "
    "how concentrated is the partner book?",
    "Prepaid float — with rates where they are, is the contribution still immaterial, or does it become a "
    "swing factor into next year?",
    "Adjusted EBITDA margin is roughly 21% — what's the path to the mid-20s, and would you slow onboarding "
    "investment to get there faster?",
]


# Inputs to the CFA guidance bridge (core.guidance_engine.guidance_bridge). Developed from the Q1
# transcript + the Q2 numbers: each metric carries the reported actual, prior quarter, prior-year
# quarter, the Street bar, the company's own quarterly guide, and — for the guided P&L lines — the
# PRIOR standing FY range and the NEW range management issues this quarter (the raise), plus YTD and
# prior-year remaining-period for the implied read. KPIs (TPV/NRR/take-rate) aren't formally guided,
# so they carry only the quarter comparisons.
_GUIDANCE_INPUTS = {
    "reporting_quarter": "Q2 2026", "prior_quarter": "Q1 2026", "prior_year_quarter": "Q2 2025",
    "order": ["rev", "eps", "ebitda", "fcf", "tpv", "nrr", "take_rate"],
    "metrics": {
        "rev": {"label": "Revenue", "unit": "$M", "fmt": "money", "actual": 25.9, "prior_q": 25.3,
                "prior_yr_q": 21.9, "prior_q_yoy_pct": 19.0, "prior_yr_yoy_pct": 22.0, "consensus": 25.7,
                "whisper": 25.85, "own_guide": [25.6, 26.0], "prior_fy_range": [103.0, 105.0],
                "new_fy_range": [104.0, 106.0], "ytd": 51.2, "prior_yr_remaining": 47.8,
                "quarters_actual": 2, "street_fy": 103.7,
                "remaining_quarters": [{"q": "Q3", "weight": 0.255, "prior_yr": 23.2},
                                       {"q": "Q4", "weight": 0.270, "prior_yr": 24.6}]},
        "eps": {"label": "Adj. EPS", "unit": "$", "fmt": "eps", "actual": 0.13, "prior_q": 0.12,
                "prior_yr_q": 0.08, "consensus": 0.12, "own_guide": [0.12, 0.13],
                "prior_fy_range": [0.52, 0.55], "new_fy_range": [0.53, 0.56], "ytd": 0.25,
                "prior_yr_remaining": 0.19, "quarters_actual": 2, "street_fy": 0.53,
                "remaining_quarters": [{"q": "Q3", "weight": 0.255, "prior_yr": 0.09},
                                       {"q": "Q4", "weight": 0.270, "prior_yr": 0.10}]},
        "ebitda": {"label": "Adj. EBITDA", "unit": "$M", "fmt": "money", "actual": 5.4, "prior_q": 5.1,
                   "prior_yr_q": 3.9, "consensus": 5.3, "own_guide": [5.2, 5.5],
                   "prior_fy_range": [21.0, 23.0], "new_fy_range": [21.5, 23.5], "ytd": 10.5,
                   "prior_yr_remaining": 8.0, "quarters_actual": 2, "street_fy": 22.0,
                   "remaining_quarters": [{"q": "Q3", "weight": 0.255, "prior_yr": 3.8},
                                          {"q": "Q4", "weight": 0.270, "prior_yr": 4.2}]},
        "fcf": {"label": "Free Cash Flow", "unit": "$M", "fmt": "money", "actual": 4.1, "prior_q": 3.6,
                "prior_yr_q": 2.4},
        "tpv": {"label": "Integrated Volume (TPV)", "unit": "$B", "fmt": "volume", "actual": 3.42,
                "prior_q": 3.29, "prior_yr_q": 2.69,
                "path_quarters": [{"q": "Q3", "value": 3.55, "prior_yr": 2.77},
                                  {"q": "Q4", "value": 3.78, "prior_yr": 2.93}]},
        "nrr": {"label": "Net Revenue Retention", "unit": "%", "fmt": "pct", "actual": 112.0,
                "prior_q": 112.0, "prior_yr_q": 111.0,
                "path_quarters": [{"q": "Q3", "value": 112.0}, {"q": "Q4", "value": 113.0}]},
        "take_rate": {"label": "Net Take-Rate", "unit": "bps", "fmt": "bps", "actual": 47.0,
                      "prior_q": 46.0, "prior_yr_q": 44.0,
                      "path_quarters": [{"q": "Q3", "value": 48.0}, {"q": "Q4", "value": 49.0}]},
    },
}


def seed_script_workflow(cid="demo"):
    """Write the demo's Q2 2026 script workflow at Northlake scale (was USIO's $102.5M / $8.9B). q2_numbers
    are developed from the Q1 transcript and include the three Street KPIs; the four persona sections are
    pre-drafted to match. Mid-flight (Exec Review active) so readiness reads real."""
    import datetime as _dt

    from core import db
    now = _dt.datetime.now()

    def _ago(days):
        return (now - _dt.timedelta(days=days)).strftime("%Y-%m-%d %H:%M")

    q2 = dict(_Q2_NUMBERS)
    q2["submitted_at"] = _ago(6)
    _persona_keys = ("ir_open", "cfo_fin", "cro_ops", "ceo_narrative")
    state = {
        "version": 1,
        "current_stage": "exec_review",
        "q2_numbers": q2,
        # Stage 1B operating metrics — Northlake's KPIs + partner-pipeline detail (not USIO's card/ACH set).
        "q2_ops_metrics": {
            "tpv": 3.42, "tpv_yoy": 27.0, "nrr": 112.0, "take_rate": 47.0, "integrated_mix": 62.0,
            "new_partner_golives": 14, "isv_in_impl": 22, "partners_live": 340, "active_merchants_k": 58.0,
            "legacy_rev_yoy": 3.0, "prepaid_float": "Stable",
            "new_verticals": "Property-management pilot live with two anchor ISV partners; membership/recreation in evaluation.",
            "disclosure_notes": "", "submitted_at": _ago(6),
        },
        "guidance_inputs": _GUIDANCE_INPUTS,   # feeds core.guidance_engine.guidance_bridge (the CFA read)
        "script_text": dict(_SCRIPT_TEXT),
        "persona_notes": {k: {"whats_new": "", "final_notes": ""} for k in _persona_keys},
        # Guidance seeded (with text) so the auto-draft doesn't regenerate it off USIO seasonality.
        "guidance_decision": {
            "decision": "RAISE",
            "text": ("Raising full-year FY2026 net-revenue guidance to $104–106M (from $103–105M) and "
                     "reiterating an adjusted EBITDA margin of roughly 21%, reflecting first-half momentum "
                     "and the back-half-weighted new-partner go-live cadence."),
        },
        "fls_checklist": {},
        "versions": [{"tag": "v1", "note": "Draft v1 — CFO numbers populated, all sections drafted",
                      "by": "Priya Raman (CFO)", "at": _ago(6)}],
        "reviewers": {r: {"status": ("complete" if r == "IR" else "pending"),
                          "sent": None, "received": (_ago(3) if r == "IR" else None), "notes": ""}
                      for r in ("IR", "CFO", "CEO", "CRO", "Legal")},
        "full_script_override": "",
        "full_script_override_saved_at": None,
        "first_pass_complete": True,
        "stages": {
            "cfo_numbers":   {"status": "complete", "completed_at": _ago(6), "notes": ""},
            "ir_review":     {"status": "complete", "completed_at": _ago(3), "notes": ""},
            "exec_review":   {"status": "active",   "completed_at": None, "notes": ""},
            "consolidate":   {"status": "pending",  "completed_at": None, "notes": ""},
            "legal_signoff": {"status": "pending",  "completed_at": None, "notes": ""},
        },
        "adversarial_qa": {
            "generated_at": _ago(2),
            "items": [{"question": q, "why": "", "angle": ""} for q in _ADVERSARIAL_QA],
        },
        "prep_vs_actual": {
            "Q1 2026": {
                "generated_at": _ago(90),
                "script": {"delivered": ["Net revenue $25.3M (+19%)", "Integrated volume +28%",
                                         "Gross margin +180 bps"],
                           "dropped": ["Gross-to-net bridge (promised, not shown)"],
                           "improvised": ["Adjacent-vertical framing"]},
                "qa": {"hits": [{"pred": "PayFac attach sustainability",
                                 "actual": "asked whether 28% is a baseline or a pull-forward"}],
                       "misses": ["Gross-to-net bridge detail", "Take-rate ceiling", "Capital allocation",
                                  "Churn / concentration", "Macro sensitivity"],
                       "surprises": ["Competitive moat vs larger processors", "Partner unit economics / LTV"],
                       "hit_rate": 22},
                "had_predictions": True, "accrued": {"new_global": 0, "new_client": 4}},
        },
    }
    db.save_json("script_workflow_state.json", state, client_id=cid)
    return len(_SCRIPT_TEXT)


def seed_earnings_demo(cid="demo"):
    n_s = seed_surprise_log(cid)
    n_t = seed_transcripts(cid)
    n_w = seed_script_workflow(cid)
    return {"surprises": n_s, "transcripts": n_t, "script_sections": n_w}


if __name__ == "__main__":
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config.client_config import reload_registry, set_active_client_id
    reload_registry()
    set_active_client_id("demo")
    out = seed_earnings_demo("demo")
    print(f"Earnings demo seeded: {out['surprises']} surprise quarters, {out['transcripts']} transcript(s), "
          f"{out['script_sections']} script sections.")
