"""
page_modules_nicegui/outreach.py — Outreach / Mail Gateway page, NiceGUI version.

Partial port: the page header is done, but render_mail_gateway_ui() (the
IMAP/SMTP configuration and email-search UI it calls in the original app) is
a ~300-line Streamlit function still living in app.py (lines 123-421) that
hasn't been ported yet — it's substantial enough to be its own task rather
than folding it into this first proof-of-concept pass. Until it's ported,
this page shows what the header/framing looks like in NiceGUI and a clear
placeholder for the part that's still pending.
"""

from nicegui import ui

from config.theme_tokens import ACTIVE as COLORS


def render_outreach_page():
    ui.html(
        "<div class='section-eyebrow'>OUTREACH</div>"
        "<div class='section-title'>Mail Gateway</div>"
    )
    ui.label(
        "Mail Gateway configuration (IMAP/SMTP setup, email search) is not yet "
        "ported to this new interface — still available in the original app "
        "(python app.py) while it's being rebuilt."
    ).style(f"color:{COLORS['text_muted']}")
