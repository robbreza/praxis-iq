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
    "meeting_confirmation": "Meeting confirmed",
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
    for cat in ("model", "research_note", "ndr_request", "speak_to_management", "conference_invite"):
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
