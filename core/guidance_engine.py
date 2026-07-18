"""core/guidance_engine.py — single source of truth for guidance analytics.

One brain, two views. The Earnings "Guidance & Outlook Decision Engine"
(page_modules_nicegui/earnings_page.py) and the Markets "Update guidance —
live impact" panel (markets_page.py) both call into here, so the seasonal
math, the implied-FY figures, the back-end-weighting test, and the
morning-after buy-side read can never diverge between the two screens.

Pure computation only — no NiceGUI. The page modules own the rendering and
consume the values/dicts these functions return. Every seasonal / growth /
prior-FY input comes from the active client's guidance_policy (CGP()); a
client with none configured gets an honest all-zeros read rather than USIO's
numbers.
"""

import re

from config.client_config import CE, CF, CGP, CT, get_active_client_id


# ─────────────────────────────────────────────────────────────────────────
# Shared primitives
# ─────────────────────────────────────────────────────────────────────────
def street_avg(period_estimates, period, field):
    """Street consensus (mean of ingested analyst estimates) for a period."""
    ests = period_estimates.get(period, {}) if period else {}
    vals = [v.get(field) for v in ests.values() if v.get("Rating") is not None and v.get(field) is not None]
    return round(sum(vals) / len(vals), 2) if vals else None


def period_year(period):
    parts = (period or "").split()
    return parts[-1] if parts else ""


def next_year_suffix(year):
    try:
        digits = "".join(c for c in year if c.isdigit())
        suffix = "".join(c for c in year if not c.isdigit())
        return f"{int(digits) + 1}{suffix}"
    except Exception:
        return ""


def reported_actuals():
    """Last reported quarter's actuals, keyed by period label (e.g. 'Q1 2026E').
    Past quarters aren't in forward guidance, so the full-year roll-up needs
    these to avoid coming up a quarter short."""
    fin = CF()
    lq = fin.get("last_quarter", "")
    if not lq:
        return {}
    key = lq if lq.endswith("E") else f"{lq}E"
    return {key: {"Revenue Est ($M)": fin.get("last_rev"),
                  "EPS Est": fin.get("last_eps"),
                  "EBITDA Est ($M)": fin.get("last_ebitda")}}


def fy_from_quarters(period_guidance, year, field, override_period=None, override_val=None,
                     quarters=("Q1", "Q2", "Q3", "Q4"), actuals=None):
    """Implied full-year figure by summing the quarters. Precedence per
    quarter: the value being edited (override) > a reported actual > the
    standing quarterly guidance."""
    actuals = actuals or {}
    total, have = 0.0, False
    for q in quarters:
        p = f"{q} {year}"
        if p == override_period and override_val is not None:
            total += override_val
            have = True
        elif actuals.get(p, {}).get(field) is not None:
            total += actuals[p][field]
            have = True
        elif period_guidance.get(p, {}).get(field) is not None:
            total += period_guidance[p][field]
            have = True
    return round(total, 2) if have else None


def seasonal_implied_fy(ytd_rev):
    """Full-year revenue implied by extrapolating H1 (YTD) at the seasonal
    weights — the same lens the Decision Engine uses. Distinct from the
    quarterly-path roll-up; showing both surfaces the reconciliation gap."""
    weights = CGP().get("seasonal_weights", {})
    h1_pct = (weights.get("Q1", 0) + weights.get("Q2", 0))
    return round(ytd_rev / h1_pct, 2) if h1_pct else None


def fmt_val(v, money):
    if v is None:
        return "—"
    return f"${v:.1f}M" if money else f"${v:.2f}"


def impact_delta(new, ref, money=True):
    """(text, color) for a guidance value vs a reference (Street or prior).
    Above reads bullish/beat (green); below reads as a miss or cut (amber);
    roughly equal is neutral."""
    if new is None or ref is None or ref == 0:
        return "—", "#94A3B8"
    d = new - ref
    unit = f"${abs(d):.1f}M" if money else f"${abs(d):.2f}"
    pct = f" ({d / ref * 100:+.1f}%)"
    if abs(d) < (0.05 if money else 0.005):
        return "in line", "#475569"
    if d > 0:
        return f"+{unit}{pct} above", "#15803D"
    return f"−{unit}{pct} below", "#B45309"


def backend_weighting(implied_fy_rev, h1_rev):
    """H2 as a share of the implied FY vs the seasonal norm — the 'is this
    back-end loaded?' test. Returns None when inputs are missing."""
    weights = CGP().get("seasonal_weights", {})
    if not (implied_fy_rev and h1_rev and weights):
        return None
    h2_rev = round(implied_fy_rev - h1_rev, 1)
    h2_pct = h2_rev / implied_fy_rev * 100
    seasonal_h2 = (weights.get("Q3", 0) + weights.get("Q4", 0)) * 100
    skew = h2_pct - seasonal_h2
    level = "heavy" if skew >= 2 else ("light" if skew <= -2 else "normal")
    return {"h2_rev": h2_rev, "h2_pct": h2_pct, "seasonal_h2": seasonal_h2,
            "skew": skew, "level": level}


def morning_read_parts(period, fy_label, new_rev, street_rev_q,
                       implied_fy_rev, prior_fy_rev, backend):
    """The 'what the buy-side detects first' narrative, assembled from the
    common ingredients. Shared verbatim by both screens so the headline can't
    say two different things."""
    parts = []
    if street_rev_q:
        d = new_rev - street_rev_q
        if d < -0.05:
            parts.append(f"{period} revenue guide ${new_rev:.1f}M lands ${abs(d):.1f}M below Street "
                         f"(${street_rev_q:.1f}M) — the tape reacts to the headline miss first.")
        elif d > 0.05:
            parts.append(f"{period} revenue guide ${new_rev:.1f}M clears Street (${street_rev_q:.1f}M) by "
                         f"${d:.1f}M — a clean beat.")
        else:
            parts.append(f"{period} revenue guide is in line with Street (${street_rev_q:.1f}M).")
    if implied_fy_rev is not None and prior_fy_rev is not None:
        dfy = implied_fy_rev - prior_fy_rev
        if dfy > 0.05:
            parts.append(f"But the implied {fy_label} rises to ${implied_fy_rev:.1f}M (+${dfy:.1f}M vs prior guide) — "
                         f"an effective FY raise even as the quarter softens: the classic 'raise the year, lower the "
                         f"quarter'.")
        elif dfy < -0.05:
            parts.append(f"The implied {fy_label} falls to ${implied_fy_rev:.1f}M (−${abs(dfy):.1f}M vs prior) — an "
                         f"effective FY cut; quarter and year read directionally consistent.")
        else:
            parts.append(f"The implied {fy_label} holds at ${implied_fy_rev:.1f}M — full year intact.")
    if backend:
        if backend["skew"] >= 2:
            parts.append(f"That pushes implied H2 to {backend['h2_pct']:.0f}% of FY versus a "
                         f"{backend['seasonal_h2']:.0f}% seasonal norm (+{backend['skew']:.0f}pp) — expect the "
                         f"hardest questions on the H2 bridge and Q4 concentration.")
        elif backend["skew"] <= -2:
            parts.append(f"H2 lands at {backend['h2_pct']:.0f}% of FY versus a {backend['seasonal_h2']:.0f}% norm "
                         f"— front-loaded and de-risked, easier to defend.")
    return parts


def apply_action(action, seasonal):
    """Translate a guidance decision verb (raise_low / raise_mid / narrow /
    reiterate) into a new FY revenue range + rationale, from the seasonal
    read's fy_low/fy_hi and the client's range_deltas policy. The single place
    a verb becomes numbers — so the Decision Engine and any quick-set elsewhere
    can never produce different ranges. Flat-dollar nudges are a per-client
    policy value (guidance_policy.range_deltas_m), 0 (no-op) if unconfigured."""
    fy_low, fy_hi = seasonal["fy_low"], seasonal["fy_hi"]
    deltas = CGP().get("range_deltas_m", {})
    d_low = deltas.get("raise_low", 0)
    d_mid = deltas.get("raise_mid", 0)
    d_narrow = deltas.get("narrow", 0)
    if action == "raise_low":
        new_low, new_hi = round(fy_low + d_low, 1), round(fy_hi, 1)
        rationale = (f"Raising the low end from ${fy_low:.1f}M to ${new_low:.1f}M reflects the Q2 beat now banked "
                     f"into the full year. The high end is maintained, preserving appropriate conservatism given "
                     f"H2 execution risk.")
    elif action == "raise_mid":
        new_low, new_hi = round(fy_low + d_mid, 1), round(fy_hi + d_mid, 1)
        rationale = (f"Raising both ends of the guidance range by approximately ${d_mid:.1f}M reflects "
                     f"strong H1 performance and improving H2 visibility from pipeline, new implementations, and "
                     f"named H2 catalysts.")
    elif action == "narrow":
        new_low, new_hi = round(fy_low + d_narrow, 1), round(fy_hi - d_narrow, 1)
        rationale = ("Narrowing the guidance range reflects increased visibility into H2 without committing to "
                     "a higher midpoint ahead of key Q3 implementations.")
    else:  # reiterate
        new_low, new_hi = round(fy_low, 1), round(fy_hi, 1)
        rationale = ("Reiterating the full-year guidance range reflects management's confidence in the business "
                     "trajectory while maintaining appropriate conservatism given that significant H2 "
                     "implementations are still scaling.")
    return new_low, new_hi, rationale


ACTION_LABELS = {
    "raise_low": "RAISE — low end", "raise_mid": "RAISE — midpoint",
    "reiterate": "REITERATE", "narrow": "NARROW range",
}


def reporting_fy_label():
    """The full-year period label for the current reporting year (e.g.
    'FY 2026E'), derived from the client's earnings date."""
    year = (CE().get("earnings_date", "") or "")[:4]
    return f"FY {year}E" if year else None


def commit_fy_guidance(new_low, new_hi, client_id=None):
    """Write a decided FY revenue range's midpoint into the canonical
    period_guidance store (preserving the existing FY EPS/EBITDA), so a
    guidance action taken in the Decision Engine flows straight through to the
    Markets consensus matrix and impact analysis — one number, one store.
    Returns the FY label written, or None if it couldn't be resolved."""
    from core import consensus
    cid = client_id or get_active_client_id()
    fy_label = reporting_fy_label()
    if not fy_label:
        return None
    cur = consensus.get_consensus(cid).get("period_guidance", {}).get(fy_label, {})
    consensus.update_guidance(
        fy_label,
        eps_est=cur.get("EPS Est"),
        revenue_est=round((new_low + new_hi) / 2, 1),
        ebitda_est=cur.get("EBITDA Est ($M)"),
        client_id=cid,
    )
    return fy_label


def current_decision(client_id=None):
    """The guidance decision on record (action + range) from the script
    workflow state — the metadata the Markets surface reads to show what was
    decided in the Decision Engine. Numbers themselves live in period_guidance."""
    from core import db
    gd = db.load_json("script_workflow_state.json", {}, client_id=client_id).get("guidance_decision", {})
    if not gd.get("action"):
        return None
    return {
        "action": gd["action"],
        "label": ACTION_LABELS.get(gd["action"], gd["action"]),
        "new_low": gd.get("new_low"),
        "new_hi": gd.get("new_hi"),
    }


def set_decision(action, client_id=None):
    """Set (or change) the guidance decision from anywhere — the Markets
    quick-set and the Decision Engine both land here, so there is exactly one
    write path for "the decision." Translates the verb to a range via
    apply_action, persists action/new_low/new_hi/rationale onto the workflow
    state (preserving any drafted script text and context), and writes the FY
    midpoint through to period_guidance. Returns a dict describing what was
    committed — including redraft_needed, True when a script section was
    already drafted for a *different* action and now no longer matches.

    The prose is DERIVED, not authored-and-left: when the decision changes, this
    REGENERATES gd["text"] from the new numbers via render_guidance_prose().

    It used to deliberately leave gd["text"] alone and merely set needs_redraft
    — "the words are authored in Script Generation". In practice that produced
    the failure it was trying to avoid: paragraphs quoting a range nobody had
    decided any more, sitting there looking authoritative, with a flag nothing
    enforced. A guidance range must have exactly one source. The previous words
    are preserved at gd["text_prev"] (nothing is lost), and ai_redraft_suggested
    invites the richer AI draft — which regenerates from these same inputs."""
    from core import db
    cid = client_id or get_active_client_id()
    ss = db.load_json("script_workflow_state.json", {}, client_id=cid)
    gd = ss.get("guidance_decision", {}) or {}
    math_ = seasonal_read(ss)
    new_low, new_hi, rationale = apply_action(action, math_)

    prev_action = gd.get("action")
    prev_text = gd.get("text")
    changed = prev_action is not None and prev_action != action
    numbers_moved = (gd.get("new_low") != new_low) or (gd.get("new_hi") != new_hi)
    # Re-deciding the SAME action must still repair prose that is already stale —
    # otherwise text left over from an earlier draft survives untouched simply
    # because nothing "changed" this time round. That is how the $93.8M–$95.5M
    # paragraph outlived the raise_mid decision that superseded it.
    already_stale = bool(prev_text) and stated_range_conflicts(prev_text, new_low, new_hi)

    gd.update({"action": action, "new_low": new_low, "new_hi": new_hi, "rationale": rationale})
    if prev_text and (changed or numbers_moved or already_stale):
        gd["text_prev"] = prev_text          # keep the old words; never silently discard
        gd["ai_redraft_suggested"] = True    # richer prose is a click away
    if prev_text is None or changed or numbers_moved or already_stale:
        gd["text"] = render_guidance_prose(action, new_low, new_hi, rationale, gd.get("context", ""))
    gd.pop("needs_redraft", None)            # can't be stale — it was just regenerated
    ss["guidance_decision"] = gd
    db.save_json("script_workflow_state.json", ss, client_id=cid)

    fy_label = commit_fy_guidance(new_low, new_hi, client_id=cid)
    return {
        "action": action,
        "label": ACTION_LABELS.get(action, action),
        "new_low": new_low,
        "new_hi": new_hi,
        "fy_label": fy_label,
        # The prose was regenerated from the new numbers, so a redraft is never
        # *needed* for correctness now. Kept in the response shape for callers,
        # and True only to signal "the richer AI draft is worth re-running".
        "redraft_needed": bool(gd.get("ai_redraft_suggested")),
        "text_regenerated": prev_text is None or changed or numbers_moved or already_stale,
    }


# ─────────────────────────────────────────────────────────────────────────
# Seasonal read — moved verbatim from earnings_page._guidance_math so the
# Decision Engine and every other consumer share one definition.
# ─────────────────────────────────────────────────────────────────────────
def render_guidance_prose(action, new_low, new_hi, rationale="", context=""):
    """Deterministically render the Guidance & Outlook prose FROM the decision.

    THE STRUCTURAL RULE: the decision (action + range) is the INPUT; this prose
    is a DERIVED artifact. It lives in core, next to set_decision(), specifically
    so changing the decision can regenerate the words in the same breath — the
    old split (decision in core, renderer in earnings_page) is exactly why prose
    could sit quoting a range nobody had decided any more.

    Every number here comes from the arguments, never from stored text, so the
    output cannot contradict the input. The page's AI drafter produces richer
    words from these SAME inputs; this is the always-correct baseline and the
    fallback when the model is unavailable.
    """
    policy = CGP()
    catalysts = policy.get("known_h2_catalysts", [])
    closing_line = (policy.get("closing_line") or "").strip()
    handoff = (policy.get("operator_handoff") or "").strip()
    growth_low, growth_high = policy.get("fy_growth_low"), policy.get("fy_growth_high")
    growth_pct = (f"{growth_low*100:.0f}%–{growth_high*100:.0f}%"
                  if growth_low is not None and growth_high is not None else "our stated")
    range_str = f"${new_low:.1f}M to ${new_hi:.1f}M"

    openers = {
        "raise_low": "Based on our strong first-half performance, we are raising the low end of our full-year revenue guidance.",
        "raise_mid": "Based on our strong first-half performance and improving second-half visibility, we are raising our full-year revenue guidance.",
        "narrow": "Based on improving visibility into the second half, we are narrowing our full-year revenue guidance range.",
        "reiterate": "We are reiterating our full-year revenue guidance.",
    }
    ranges = {
        "raise_low": f"[FLS] We now expect full-year revenue in the range of {range_str}, reflecting the Q1 and Q2 performance now banked into the year. [/FLS]",
        "raise_mid": f"[FLS] We now expect full-year revenue in the range of {range_str}. [/FLS]",
        "narrow": f"[FLS] We now expect full-year revenue in the range of {range_str}. [/FLS]",
        # Even "reiterate" states the range explicitly. The old variant said only
        # "continues to expect {growth}% growth", which let a stale range from an
        # earlier draft survive underneath — the range must always be restated
        # from the input so there is exactly one number in play.
        "reiterate": f"[FLS] We continue to expect full-year revenue in the range of {range_str}, "
                     f"representing {growth_pct} growth, while also anticipating continued positive adjusted EBITDA. [/FLS]",
    }
    tones = {
        "raise_low": "This raise reflects the beat delivered through the first half of the year. The high end of our range is maintained, as significant H2 implementations are still ramping and we believe it is appropriate to retain some conservatism ahead of Q3 and Q4 execution.",
        "raise_mid": "This raise reflects confidence in our second-half execution across pipeline conversion, new implementations, and program ramps.",
        "narrow": "Narrowing the range reflects improving visibility without getting ahead of H2 execution.",
        "reiterate": "We believe it is prudent to maintain our full range as key H2 implementations continue to scale.",
    }
    h2_signal = ("[FLS] We expect the second half of the year to be sequentially stronger than the first half as "
                 "implementations currently in progress begin to scale and as newer initiatives contribute more "
                 "meaningfully to our revenue base. [/FLS]")
    catalysts_block = "\n".join(f"  {c}" for c in catalysts) or "  [No H2 catalysts configured for this client]"
    closing_bit = f"I thank our shareholders for their trust and support. {closing_line}\n\n" if closing_line else ""
    ctx_bit = f"{context.strip()}\n\n" if (context or "").strip() else ""
    rat_bit = f"{rationale.strip()}\n\n" if (rationale or "").strip() else ""

    return (
        f"{openers.get(action, openers['reiterate'])}\n\n"
        f"{ranges.get(action, ranges['reiterate'])}\n\n"
        f"{tones.get(action, tones['reiterate'])}\n\n"
        f"{rat_bit}{h2_signal}\n\n"
        f"[SPECIFIC H2 CATALYST LANGUAGE — reference at least 2 named catalysts here]\n"
        f"[CFO to confirm which are disclosure-appropriate before delivery:]\n{catalysts_block}\n"
        f"  [Add any Q2-specific new wins from Stage 1 notes]\n\n"
        f"{ctx_bit}{closing_bit}{handoff or ''}"
    )


# Matches a stated full-year range: "$93.8 million to $95.5 million", "$95.3M–$97.0M".
_RANGE_RE = re.compile(
    r"\$?\s*(\d{2,3}(?:\.\d)?)\s*(?:million|M)\b\s*(?:to|through|and|[-–—])\s*\$?\s*(\d{2,3}(?:\.\d)?)\s*(?:million|M)\b",
    re.I)

# Lead-in wording that makes a non-matching range a deliberate HISTORICAL
# reference rather than a stale figure.
_HISTORICAL_RE = re.compile(
    r"\b(prior|previous|previously|up from|down from|versus our|vs\.? our|"
    r"compared (?:to|with)|was|had been|last quarter'?s?|original)\b[^.]*$", re.I)


def stated_range_conflicts(text, lo, hi):
    """True if `text` states a full-year range that isn't (lo, hi), ignoring
    ranges the sentence explicitly frames as history ("up from our prior range
    of …"). Shared by set_decision (to decide whether prose needs regenerating)
    and guidance_consistency (to report), so both agree on what 'stale' means."""
    if lo is None or hi is None or not text:
        return False
    for m in _RANGE_RE.finditer(text):
        a, b = float(m.group(1)), float(m.group(2))
        if abs(a - float(lo)) <= 0.05 and abs(b - float(hi)) <= 0.05:
            continue
        if _HISTORICAL_RE.search(text[max(0, m.start() - 45):m.start()].lower()):
            continue
        return True
    return False


def guidance_consistency(client_id=None):
    """Verify every FY guidance range stated anywhere in the script matches the
    ONE authoritative input — the CFO's guidance decision (action → new_low /
    new_hi, set via set_decision()).

    WHY THIS EXISTS: the numbers are single-source, but the PROSE isn't.
    set_decision() deliberately doesn't touch gd["text"] (the words are authored
    by a human), so re-deciding the action leaves previously-authored paragraphs
    quoting the OLD range. needs_redraft flags that, but nothing enforces it —
    and personas can hand-type a range of their own on top. The result is several
    "attempts at guidance" coexisting in one script, each looking authoritative.
    This reads the input, scans every piece of prose for a stated range, and
    reports anything that disagrees. Returns:
      {input:{action,low,hi}, needs_redraft, conflicts:[{source,stated,excerpt}],
       sources_scanned:[str], ok:bool}
    """
    from core import db
    cid = client_id or get_active_client_id()
    ss = db.load_json("script_workflow_state.json", {}, client_id=cid) or {}
    gd = ss.get("guidance_decision") or {}
    lo, hi = gd.get("new_low"), gd.get("new_hi")

    sources = {"guidance_decision.text": gd.get("text") or ""}
    for k, v in (ss.get("script_text") or {}).items():
        sources[f"script_text.{k}"] = v or ""
    if ss.get("full_script_override"):
        sources["full_script_override"] = ss["full_script_override"]

    conflicts = []
    for name, text in sources.items():
        for m in _RANGE_RE.finditer(text or ""):
            a, b = float(m.group(1)), float(m.group(2))
            if lo is None or hi is None:
                continue  # no decision to compare against yet
            if abs(a - float(lo)) <= 0.05 and abs(b - float(hi)) <= 0.05:
                continue  # matches the input — fine
            # A range can legitimately differ from the input when the sentence is
            # explicitly citing HISTORY ("up from our prior range of $93.8M to
            # $95.5M"). That's correct context, not a stale number — flagging it
            # would train the reader to ignore this check.
            lead = text[max(0, m.start() - 45):m.start()].lower()
            if _HISTORICAL_RE.search(lead):
                continue
            s = max(0, m.start() - 60)
            conflicts.append({
                "source": name,
                "stated": f"${a:.1f}M–${b:.1f}M",
                "excerpt": "…" + " ".join(text[s:m.end() + 40].split()) + "…",
            })
    return {
        "input": {"action": gd.get("action"), "low": lo, "hi": hi,
                  "rationale": gd.get("rationale")},
        "needs_redraft": bool(gd.get("needs_redraft")),
        "conflicts": conflicts,
        "sources_scanned": sorted(sources),
        "ok": not conflicts and not gd.get("needs_redraft"),
    }


def seasonal_read(ss):
    """Seasonality-adjusted guidance numbers + scenario recommendation, from
    the reported-quarter actuals in `ss` (script_workflow_state) plus the
    client's guidance policy. The recommendation is informational — the CFO/
    CEO still make the call in the Decision Engine."""
    policy = CGP()
    prior_fy_rev = policy.get("prior_fy_quarterly_revenue", {})
    weights = policy.get("seasonal_weights", {})
    growth_low = policy.get("fy_growth_low", 0)
    growth_high = policy.get("fy_growth_high", 0)
    prior_fy_total = sum(prior_fy_rev.values())

    n = ss.get("q2_numbers", {})
    q2_actual = n.get("rev", 0) or 0
    q1_actual = CF().get("last_rev", 0) or 0
    ytd_rev = q1_actual + q2_actual
    fy_low = round(prior_fy_total * (1 + growth_low), 2)
    fy_hi = round(prior_fy_total * (1 + growth_high), 2)
    fy_mid = round((fy_low + fy_hi) / 2, 2)
    ytd_pct_of_mid = (ytd_rev / fy_mid * 100) if fy_mid else 0
    seasonal_h1_pct = (weights.get("Q1", 0) + weights.get("Q2", 0)) * 100
    pace_vs_seasonal = ytd_pct_of_mid - seasonal_h1_pct
    from core import market_data
    beat_vs_street = q2_actual - (market_data.consensus_rev_value() or 0)
    h2_2025_rev = prior_fy_rev.get("Q3", 0) + prior_fy_rev.get("Q4", 0)
    h2_needed_low = fy_low - ytd_rev
    h2_growth_needed = ((h2_needed_low / h2_2025_rev) - 1) * 100 if h2_2025_rev else 0
    fy_implied_from_h1 = (ytd_rev / seasonal_h1_pct * 100) if seasonal_h1_pct else 0

    w_q3, w_q4 = weights.get("Q3", 0), weights.get("Q4", 0)
    prior_q3, prior_q4 = prior_fy_rev.get("Q3", 0), prior_fy_rev.get("Q4", 0)
    q3_target_mid = round(fy_mid * w_q3, 1)
    q4_target_mid = round(fy_mid * w_q4, 1)
    q3_target_low = round(fy_low * w_q3, 1)
    q4_target_low = round(fy_low * w_q4, 1)
    q3_yoy_needed = ((q3_target_low / prior_q3) - 1) * 100 if prior_q3 else 0
    q4_yoy_needed = ((q4_target_low / prior_q4) - 1) * 100 if prior_q4 else 0

    prior_fy_label = policy.get("prior_fy_label", "prior FY")
    report_q = "Q2"
    prior_rq = prior_fy_rev.get(report_q, 0)
    prior_rq_share = (prior_rq / prior_fy_total * 100) if prior_fy_total else 0
    rq_weight_pct = weights.get(report_q, 0) * 100
    comp_gap = rq_weight_pct - prior_rq_share
    if comp_gap >= 3:
        comp_note = (f"Prior-year {report_q} ({prior_fy_label}) landed at {prior_rq_share:.0f}% of FY vs its "
                     f"{rq_weight_pct:.0f}% seasonal norm ({comp_gap:+.0f}pp light) — this year's YoY comp is "
                     f"flattering. Acknowledge the easy comp in the script.")
    elif comp_gap <= -3:
        comp_note = (f"Prior-year {report_q} ran {abs(comp_gap):.0f}pp above its seasonal norm — this year's YoY "
                     f"comp is tough. Frame growth against the strong prior-year base.")
    else:
        comp_note = ""

    if pace_vs_seasonal >= 3.0 and beat_vs_street >= 1.0:
        scenario, label = "RAISE_MID", "RAISE MIDPOINT — Running materially above seasonal pace; beat supports full range shift"
    elif pace_vs_seasonal >= 1.0 and beat_vs_street >= 0:
        scenario, label = "RAISE_LOW", "RAISE LOW END — Above seasonal pace; bank the beat into the floor"
    elif pace_vs_seasonal >= -1.0 and beat_vs_street >= -0.5:
        scenario, label = "REITERATE", "REITERATE — On seasonal pace; H2 catalysts needed before raising"
    else:
        scenario, label = "REITERATE_CAUTIOUS", "REITERATE WITH CAUTION — Behind seasonal pace; Street will ask about H2 bridge"

    return {
        "ytd_rev": ytd_rev, "fy_low": fy_low, "fy_hi": fy_hi, "fy_mid": fy_mid,
        "ytd_pct_of_mid": ytd_pct_of_mid, "pace_vs_seasonal": pace_vs_seasonal,
        "beat_vs_street": beat_vs_street, "h2_2025_rev": h2_2025_rev,
        "h2_needed_low": h2_needed_low, "h2_growth_needed": h2_growth_needed,
        "fy_implied_from_h1": fy_implied_from_h1, "scenario": scenario, "scenario_label": label,
        "q3_target_mid": q3_target_mid, "q4_target_mid": q4_target_mid,
        "q3_target_low": q3_target_low, "q4_target_low": q4_target_low,
        "q3_yoy_needed": q3_yoy_needed, "q4_yoy_needed": q4_yoy_needed,
        "comp_note": comp_note, "prior_fy_label": prior_fy_label,
    }
