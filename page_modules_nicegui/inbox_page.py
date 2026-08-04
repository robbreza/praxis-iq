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
    ui.label("IR Inbox").classes("text-2xl font-bold").style(f"color:{COLORS['text_heading']};")

    # Connection / auto-sync status — makes the poller visible.
    from core import mail_gateway
    if mail_gateway.is_configured():
        _h, _p, user, _pw = mail_gateway.get_imap_config()
        every = os.environ.get("MAIL_INBOX_POLL_MINUTES", "5")
        auto = bool(os.environ.get("MAIL_INBOX_CLIENT_IDS"))
        note = (f"Connected to {user}. Models, research notes and requests emailed here are parsed and filed "
                + (f"automatically — checked every {every} min."
                   if auto else "when you Sync the inbox (Investor Targeting → Meeting Hub)."))
    else:
        note = ("The IR inbox isn’t connected yet. Once IMAP credentials are set, anything emailed to your "
                "IR mailbox — a model, a research note, an NDR ask — is parsed and lands here for review.")
    ui.label(note).style(f"color:{COLORS['text_muted']};font-size:13px;margin-bottom:6px;")

    from core import inbox_queue
    pending = inbox_queue.list_pending_items()

    if pending:
        # Same category-specific confirm/dismiss cards used in Investor Targeting.
        from page_modules_nicegui.investors_page import _render_pending_inbox_items
        _render_pending_inbox_items()
    else:
        with ui.card().classes("w-full").style(
                f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"
                f"border-left:4px solid {COLORS['accent']};margin-top:10px;"):
            ui.label("Inbox is clear").classes("font-bold").style(f"color:{COLORS['text_heading']};")
            ui.label("Nothing waiting on you. Email a model (.xlsx / .pdf) or a research note to your IR "
                     "mailbox and it appears here — parsed, with the numbers pulled out, ready to file.").style(
                f"color:{COLORS['text_muted']};font-size:13px;")

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
        ui.label("Recently filed").classes("section-head").style("margin-top:18px;")
        for it in recent:
            with ui.card().classes("w-full").style(
                    f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};padding:6px 12px;"):
                with ui.row().classes("w-full justify-between items-center"):
                    ui.label(f"{_cat_label(it.get('category'))}  ·  "
                             f"{it.get('firm') or it.get('contact') or '—'}").style(
                        f"color:{COLORS['text_body']};font-size:12px;font-weight:600;")
                    ui.label(it.get("received_at", "")).style(f"color:{COLORS['text_muted']};font-size:11px;")
                if it.get("subject"):
                    ui.label(it["subject"]).style(f"color:{COLORS['text_muted']};font-size:12px;")

    _render_ir_knowledge_editor()


def _render_ir_knowledge_editor():
    """The approved-answer knowledge base editor — the public answers the shareholder-reply
    drafter is allowed to state directly. Every entry is IR-approved public info."""
    from config.client_config import get_active_client_id
    from core import ir_knowledge, ui_context
    cid = get_active_client_id()
    _ro = ui_context.is_read_only()  # capture once — a rebuild fires from callbacks (unbound context)

    with ui.expansion("Approved answers — used when drafting shareholder replies", icon="menu_book").classes(
            "w-full").style("margin-top:18px;"):
        ui.label("Pre-vetted PUBLIC answers the reply drafter may state directly — dividend policy, transfer "
                 "agent, filing locations, how to reach IR. Anything not here defers to your filings; nothing "
                 "is invented. Keep every answer to publicly disclosed information.").style(
            f"color:{COLORS['text_muted']};font-size:11.5px;")
        _box = ui.column().classes("w-full gap-1").style("margin-top:6px;")

        def _rebuild():
            _box.clear()
            with _box:
                for e in ir_knowledge.load_entries(cid):
                    with ui.card().classes("w-full").style(
                            f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};padding:8px 10px;"):
                        if _ro:
                            ui.label(e.get("topic") or "").style(f"color:{COLORS['text_heading']};font-size:12px;font-weight:600;")
                            ui.label(e.get("answer") or "").style(f"color:{COLORS['text_body']};font-size:12px;")
                            continue
                        _t = ui.input("Topic", value=e.get("topic") or "").props("outlined dense").classes(
                            "w-full").style("font-size:12px;")
                        _a = ui.textarea("Answer", value=e.get("answer") or "").props("outlined autogrow dense").classes(
                            "w-full").style("font-size:12px;")
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
                            f"color:{COLORS['text_body']};font-size:12px;font-weight:600;")
                        _nt = ui.input("Topic (e.g. Dividend policy)").props("outlined dense").classes(
                            "w-full").style("font-size:12px;")
                        _na = ui.textarea("Answer (public info only)").props("outlined autogrow dense").classes(
                            "w-full").style("font-size:12px;")

                        def _add(_nt=_nt, _na=_na):
                            if not (_nt.value and _na.value):
                                ui.notify("Topic and answer are both required.", type="warning")
                                return
                            ir_knowledge.add_entry(_nt.value, _na.value, cid)
                            ui.notify("Added to the knowledge base.", type="positive")
                            _rebuild()
                        ui.button("Add answer", icon="add", on_click=_add).props("color=primary dense").style("margin-top:4px;")
        _rebuild()
