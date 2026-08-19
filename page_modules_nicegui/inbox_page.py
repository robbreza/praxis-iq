"""page_modules_nicegui/inbox_page.py — the IR Inbox.

The front door to the email-ingestion pipeline (core/mail_gateway.py ->
core/email_classifier.py -> core/inbox_queue.py + core/documents.py). It
consolidates the models / research notes / requests parsed out of the IR
mailbox, so "go to my inbox" is a real destination in the nav.

The pending-review cards REUSE investors_page._render_pending_inbox_items()
verbatim, so this is a front door onto the existing review flow, not a fork of
it. Below that, a short "recently filed" history keeps the ingestion visible
even when the queue is clear.
"""
import os

from nicegui import ui

from config.theme_tokens import ACTIVE as COLORS

_CAT_LABELS = {
    "model": "Model", "research_note": "Research note", "ndr_request": "NDR request",
    "speak_to_management": "Mgmt request", "conference_invite": "Conference invite",
    "meeting_confirmation": "Meeting confirmed", "shareholder_inquiry": "Shareholder inquiry",
}


def _cat_label(c):
    return _CAT_LABELS.get(c, (c or "Item").replace("_", " ").title())


def render_inbox_page():
    from page_modules_nicegui.signals import capability_banner
    ui.label("IR Inbox").classes("text-2xl font-bold").style(f"color:{COLORS['text_heading']};")
    capability_banner(
        "Every investor email, read and filed",
        "Models, research notes, and meeting/NDR requests emailed to your IR mailbox are auto-parsed "
        "and filed here for one-click confirmation.",
        tag="AI mail classification", compact=True)
    ui.element("div").style("height:10px;")

    # One compact action bar. The Sync action lives HERE now — it previously existed only on the
    # Meeting Hub, so this page told you to go sync somewhere else (a broken flow). The connection
    # facts ride alongside as a status chip instead of a prose paragraph re-explaining the pipeline.
    from core import mail_gateway

    def _do_sync():
        if not mail_gateway.is_configured():
            ui.notify("IR inbox isn’t connected yet — add IMAP credentials in .env.", type="warning")
            return
        from config.client_config import CA, get_active_client_id
        from data.seed.institution_contacts import get_institution_contacts
        lookup = {}
        for firm_name, info in (get_institution_contacts() or {}).items():
            if info.get("email"):
                lookup[info["email"].lower()] = {"name": info.get("name"), "firm": firm_name, "kind": "institution"}
        for a in CA():
            if a.get("email"):
                lookup[a["email"].lower()] = {"name": a.get("name"), "firm": a.get("firm"), "kind": "analyst"}
        result = mail_gateway.sync_inbox(lookup, client_id=get_active_client_id())
        if not result.get("ok"):
            ui.notify(result.get("message", "Sync failed."), type="warning")
            return
        msgs = result.get("messages", [])
        routed = sum(1 for m in msgs if m.get("category") != "general")
        if msgs:
            ui.notify(f"Synced — {len(msgs)} message(s)"
                      + (f" · {routed} flagged for review below." if routed else " · nothing new to review."))
        else:
            ui.notify("Synced — no new messages from known contacts.")
        ui.timer(0.9, lambda: ui.run_javascript("location.reload()"), once=True)   # reveal newly-filed items

    _configured = mail_gateway.is_configured()
    with ui.row().classes("w-full items-center gap-3").style("margin-bottom:10px;"):
        _btn = ui.button("Sync inbox", icon="sync", on_click=_do_sync).props("unelevated dense").style(
            f"background:{COLORS['accent']};color:#fff;")
        if not _configured:
            _btn.props("disable")
        if _configured:
            _h, _p, user, _pw = mail_gateway.get_imap_config()
            every = os.environ.get("MAIL_INBOX_POLL_MINUTES", "5")
            auto = bool(os.environ.get("MAIL_INBOX_CLIENT_IDS"))
            _chip = f"{user}  ·  " + (f"auto-checked every {every} min" if auto else "manual sync")
        else:
            _chip = "Not connected — add IMAP credentials in .env to start ingesting mail"
        ui.label(_chip).style(
            f"background:{COLORS['surface_hover_bg']};color:{COLORS['text_secondary']};"
            "border-radius:999px;padding:4px 12px;font-size:var(--fs-xs);white-space:nowrap;")

    # ── Meetings — the Meeting Hub lives here now (moved out of NDR/CRM) so the inbox is the single
    #    meeting front door: schedule and track 1×1s right where the parsed requests land just below.
    ui.label("Meetings").classes("section-head").style("margin-top:14px;")
    from page_modules_nicegui.investors_page import _render_meeting_hub_tab
    _render_meeting_hub_tab()

    from core import inbox_queue
    pending = inbox_queue.list_pending_items()
    # Meeting-scheduling requests are surfaced by the Meeting Hub above; exclude them from the "Needs
    # you" zone below so a request card never appears twice on this one page.
    _MEETING_CATS = ("speak_to_management", "meeting_confirmation")
    _needs_you_pending = [p for p in pending if p.get("category", "general") not in _MEETING_CATS]

    # One header system so the page reads as two clear zones (act-on-this over archive) instead of a
    # flat stack of differently-styled blocks. The count pill turns accent ONLY when something needs
    # you — the single reserved use of the accent colour on this page.
    def _zone_head(title, count=None):
        with ui.row().classes("w-full items-center gap-2").style(
                f"margin:22px 0 10px;padding-bottom:6px;border-bottom:1px solid {COLORS['border']};"):
            ui.label(title.upper()).style(
                f"color:{COLORS['text_heading']};font-size:var(--fs-sm);font-weight:700;"
                "text-transform:uppercase;letter-spacing:.06em;")
            if count is not None:
                _hot = count > 0
                ui.label(str(count)).style(
                    f"background:{COLORS['accent'] if _hot else COLORS['surface_hover_bg']};"
                    f"color:{'#fff' if _hot else COLORS['text_muted']};border-radius:999px;"
                    "padding:1px 9px;font-size:var(--fs-2xs);font-weight:700;min-width:20px;text-align:center;")

    # ══ ZONE 1 · Needs you — parsed items + open meeting/NDR requests awaiting a decision ══
    try:
        from page_modules_nicegui.investors_page import _load_ndr_requests
        _open_reqs = len([r for r in (_load_ndr_requests() or []) if not r.get("resolved")])
    except Exception:
        _open_reqs = 0
    _zone_head("Needs you", count=len(_needs_you_pending) + _open_reqs)

    if _needs_you_pending:
        # Same category-specific confirm/dismiss cards used in Investor Targeting — minus the meeting
        # categories, which the Meeting Hub section above already renders.
        from page_modules_nicegui.investors_page import _render_pending_inbox_items
        _render_pending_inbox_items(exclude=_MEETING_CATS)
    else:
        # Quiet empty state — no accent rail (nothing to act on), so the accent stays meaningful.
        with ui.card().classes("w-full").style(
                f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"):
            ui.label("Nothing waiting on you — parsed emails land here for one-click confirmation.").style(
                f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")

    # Inbound NDR / Meeting Requests — a confirmed NDR-request email lands in this list, where you
    # reply / schedule / resolve it. Refreshable so those actions repaint just this section.
    from page_modules_nicegui.investors_page import _render_ndr_requests_tab

    @ui.refreshable
    def _ndr_requests_section():
        _render_ndr_requests_tab(refresh_fn=_ndr_requests_section.refresh)
    _ndr_requests_section()

    # ══ ZONE 2 · Filed — the searchable archive of everything already handled ══
    _zone_head("Filed")

    # Recently filed — a short history so the ingestion is visible even when the queue is clear.
    recent = []
    for cat in ("model", "research_note", "ndr_request", "speak_to_management", "conference_invite",
                "shareholder_inquiry"):
        for it in (inbox_queue.list_items_by_category(cat) or []):
            if it.get("status") != "pending":
                recent.append(it)
    recent.sort(key=lambda i: i.get("received_at", ""), reverse=True)
    recent = recent[:12]
    if recent:
        ui.label("Recently filed").classes("section-head").style("margin-top:4px;")

        def _fill_filed(exp, it):
            # Build a filed row's detail (subject / sender / attachment / full body) only the FIRST
            # time it's expanded. ui.expansion renders its children eagerly into the DOM, so without
            # this every collapsed archive row would ship its ≤2KB body on the initial render. A
            # collapsed row now costs just its header; the body streams in on demand.
            if not exp.value or getattr(exp, "_filled", False):
                return
            exp._filled = True
            with exp:
                if it.get("subject"):
                    ui.label(it["subject"]).style(f"color:{COLORS['text_body']};font-size:var(--fs-base);font-weight:600;")
                if it.get("outcome"):
                    ui.label(f"Filed: {it['outcome']}").style(f"color:{COLORS['accent']};font-size:var(--fs-sm);")
                if it.get("sender_email"):
                    ui.label(f"From: {it['sender_email']}").style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
                if it.get("filename"):
                    ui.label(f"Attachment: {it['filename']}").style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
                if it.get("body"):
                    ui.label(it["body"]).style(
                        f"color:{COLORS['text_muted']};font-size:var(--fs-sm);white-space:pre-wrap;margin-top:4px;")
                if not any(it.get(k) for k in ("subject", "outcome", "sender_email", "filename", "body")):
                    ui.label("No further detail captured for this item.").style(
                        f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")

        for it in recent:
            # Expandable so a filed row isn't a dead end — tap to see what it was, where it was
            # filed, and the original text, without leaving the inbox. Body is filled lazily.
            _hdr = f"{_cat_label(it.get('category'))}  ·  {it.get('firm') or it.get('contact') or '—'}"
            _exp = ui.expansion(_hdr, caption=it.get("received_at", "")).classes("w-full").style(
                    f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};border-radius:8px;")
            _exp.on_value_change(lambda e, exp=_exp, it=it: _fill_filed(exp, it))

    _render_research_library()
    _render_ir_knowledge_editor()


def _render_research_library():
    """The analyst repository — every model and research note ever filed (from the IR inbox or
    uploaded), in one searchable, downloadable archive. Reads core/documents.py (the same store the
    inbox sync writes to and the Meeting Hub reads 'the latest model' from), so this is the browse
    view over what was previously only reachable per-firm or per-inbox-item."""
    from core import documents
    from page_modules_nicegui.investors_page import _open_attachment_preview

    docs = (documents.list_documents(doc_type="model") or []) + \
           (documents.list_documents(doc_type="research_note") or [])
    docs.sort(key=lambda d: str(d.get("uploaded_at") or ""), reverse=True)

    ui.label("Research Library").classes("section-head").style("margin-top:18px;")
    ui.label("Every analyst model and research note filed from the inbox or uploaded — one searchable "
             "archive, so you never dig through email for “the last model.”").style(
        f"color:{COLORS['text_muted']};font-size:var(--fs-sm);margin-bottom:6px;")

    if not docs:
        with ui.card().classes("w-full").style(
                f"background:{COLORS['surface_bg']};border:1px dashed {COLORS['border']};"):
            ui.label("No models or research notes filed yet.").style(f"color:{COLORS['text_muted']};")
        return

    _TYPE = {"model": ("Model", COLORS["accent"]), "research_note": ("Research note", COLORS["positive"])}
    state = {"type": "all", "q": "", "show_all": False}
    _CAP = 20   # cap the always-visible archive on first paint; a large tenant can have hundreds of docs

    with ui.row().classes("w-full items-center gap-3").style("margin-bottom:6px;flex-wrap:wrap;"):
        _toggle = ui.toggle({"all": "All", "model": "Models", "research_note": "Research notes"},
                            value="all").props("no-caps dense")
        _search = ui.input(placeholder="Search firm, analyst or file…").props("dense outlined clearable").classes(
            "flex-1").style("min-width:220px;")

    lib = ui.column().classes("w-full gap-2")

    def _download(doc_id):
        result = documents.get_document_bytes(doc_id)
        if result:
            fname, _ctype, raw = result
            ui.download(raw, filename=fname)

    def _render():
        lib.clear()
        q = (state["q"] or "").lower().strip()
        rows = [d for d in docs
                if (state["type"] == "all" or d.get("doc_type") == state["type"])
                and (not q or q in f"{d.get('firm') or ''} {d.get('contact') or ''} {d.get('filename') or ''}".lower())]
        shown = rows if (state["show_all"] or len(rows) <= _CAP) else rows[:_CAP]
        with lib:
            _cnt = f"{len(rows)} document{'s' if len(rows) != 1 else ''}"
            if len(shown) < len(rows):
                _cnt += f"  ·  showing {len(shown)}"
            ui.label(_cnt).style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
            for d in shown:
                _lbl, _col = _TYPE.get(d.get("doc_type"), ("Document", COLORS["text_muted"]))
                with ui.row().classes("w-full items-center gap-3").style(
                        f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"
                        "border-radius:8px;padding:8px 10px;"):
                    ui.label(_lbl.upper()).style(
                        f"background:{_col}22;color:{_col};font-size:var(--fs-micro);font-weight:700;"
                        "letter-spacing:.04em;padding:2px 8px;border-radius:10px;white-space:nowrap;")
                    with ui.column().classes("gap-0 flex-1").style("min-width:0;"):
                        _who = " · ".join(x for x in (d.get("firm"), d.get("contact")) if x) or "—"
                        ui.label(_who).style(f"color:{COLORS['text_body']};font-size:var(--fs-base);font-weight:600;")
                        _meta = " · ".join(x for x in (d.get("filename"), str(d.get("uploaded_at") or "")[:10],
                                                       d.get("source")) if x)
                        ui.label(_meta).style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
                    ui.button("Preview", icon="visibility",
                              on_click=lambda i=d["id"], f=d.get("filename"): _open_attachment_preview(i, f)).props(
                        "flat dense size=sm").style(f"color:{COLORS['accent_light']};font-size:var(--fs-xs);")
                    ui.button("Download", icon="download",
                              on_click=lambda i=d["id"]: _download(i)).props("flat dense size=sm").style(
                        f"color:{COLORS['accent_light']};font-size:var(--fs-xs);")
            if len(shown) < len(rows):
                ui.button(f"Show all {len(rows)}", icon="unfold_more",
                          on_click=lambda: (state.update(show_all=True), _render())).props(
                    "flat dense no-caps").style(f"color:{COLORS['accent_light']};font-size:var(--fs-xs);")

    # Changing the filter re-collapses to the cap so a narrowed result never starts fully expanded.
    _toggle.on_value_change(lambda e: (state.update(type=e.value, show_all=False), _render()))
    _search.on_value_change(lambda e: (state.update(q=e.value or "", show_all=False), _render()))
    _render()


def _render_ir_knowledge_editor():
    """The approved-answer knowledge base editor — the public answers the shareholder-reply
    drafter is allowed to state directly. Every entry is IR-approved public info."""
    from config.client_config import get_active_client_id
    from core import ir_knowledge, ui_context
    cid = get_active_client_id()
    _ro = ui_context.is_read_only()  # capture once — a rebuild fires from callbacks (unbound context)

    _exp = ui.expansion("Approved answers — used when drafting shareholder replies", icon="menu_book").classes(
            "w-full").style("margin-top:18px;")
    with _exp:
        ui.label("Pre-vetted PUBLIC answers the reply drafter may state directly — dividend policy, transfer "
                 "agent, filing locations, how to reach IR. Anything not here defers to your filings; nothing "
                 "is invented. Keep every answer to publicly disclosed information.").style(
            f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
        _box = ui.column().classes("w-full gap-1").style("margin-top:6px;")

        def _rebuild():
            _box.clear()
            with _box:
                for e in ir_knowledge.load_entries(cid):
                    with ui.card().classes("w-full").style(
                            f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};padding:8px 10px;"):
                        if _ro:
                            ui.label(e.get("topic") or "").style(f"color:{COLORS['text_heading']};font-size:var(--fs-sm);font-weight:600;")
                            ui.label(e.get("answer") or "").style(f"color:{COLORS['text_body']};font-size:var(--fs-sm);")
                            continue
                        _t = ui.input("Topic", value=e.get("topic") or "").props("outlined dense").classes(
                            "w-full").style("font-size:var(--fs-sm);")
                        _a = ui.textarea("Answer", value=e.get("answer") or "").props("outlined autogrow dense").classes(
                            "w-full").style("font-size:var(--fs-sm);")
                        with ui.row().classes("gap-2"):
                            def _save(eid=e["id"], _t=_t, _a=_a):
                                ir_knowledge.update_entry(eid, _t.value, _a.value, cid)
                                ui.notify("Saved.", type="positive")

                            def _del(eid=e["id"]):
                                ir_knowledge.delete_entry(eid, cid)
                                ui.notify("Removed.")
                                _rebuild()
                            ui.button("Save", icon="save", on_click=_save).props("flat dense color=primary")
                            ui.button("Remove", icon="delete", on_click=_del).props("flat dense").style(
                                f"color:{COLORS['danger']};")
                if not _ro:
                    with ui.card().classes("w-full").style(
                            f"background:{COLORS['surface_hover_bg']};border:1px dashed {COLORS['border']};padding:8px 10px;"):
                        ui.label("Add an approved answer").style(
                            f"color:{COLORS['text_body']};font-size:var(--fs-sm);font-weight:600;")
                        _nt = ui.input("Topic (e.g. Dividend policy)").props("outlined dense").classes(
                            "w-full").style("font-size:var(--fs-sm);")
                        _na = ui.textarea("Answer (public info only)").props("outlined autogrow dense").classes(
                            "w-full").style("font-size:var(--fs-sm);")

                        def _add(_nt=_nt, _na=_na):
                            if not (_nt.value and _na.value):
                                ui.notify("Topic and answer are both required.", type="warning")
                                return
                            ir_knowledge.add_entry(_nt.value, _na.value, cid)
                            ui.notify("Added to the knowledge base.", type="positive")
                            _rebuild()
                        ui.button("Add answer", icon="add", on_click=_add).props("color=primary dense").style("margin-top:4px;")

        # Build the (input-heavy: ~2 Quasar fields per entry) editor only when the section is first
        # opened. It's collapsed on load, so eagerly rendering every entry's Topic/Answer inputs was
        # the single largest chunk of this page's initial WebSocket payload.
        def _lazy_build(_=None):
            if _exp.value and not getattr(_exp, "_built", False):
                _exp._built = True
                _rebuild()
        _exp.on_value_change(_lazy_build)
