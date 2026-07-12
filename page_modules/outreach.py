"""
page_modules/outreach.py — Outreach / Mail Gateway page.

Extracted from the "elif page == 'Outreach':" branch of the original
single-file app.py. render_mail_gateway_ui() is still defined in app.py
itself for now (not yet moved to services/mail_gateway.py — that's a
follow-up cleanup once the services/ layer gets its own extraction pass),
so this module imports the app module itself rather than a specific name
from it, and only touches app.<name> at call time inside the render
function below — by then app.py has finished loading, so there's no
circular-import problem even though app.py also imports THIS module.

Note: this package is named "page_modules", not "pages" — a folder
literally named "pages" next to app.py triggers Streamlit's own automatic
multipage navigation, which would conflict with this app's existing custom
sidebar nav (see HANDOFF/build notes). Keep it "page_modules".
"""

import streamlit as st
import app


def render_outreach_page():
    st.markdown("<div style='padding:16px 4px 0;'><div class='section-eyebrow'>OUTREACH</div><div class='section-title'>Mail Gateway</div></div>", unsafe_allow_html=True)
    if st.session_state.get("highlight_outreach_reason"):
        st.markdown(
            f"<div style='background:#1E3A5F;border:1px solid #3B82F6;border-radius:8px;padding:10px 16px;margin:10px 4px;'>"
            f"📍 {st.session_state['highlight_outreach_reason']}"
            f"</div>", unsafe_allow_html=True
        )
        st.session_state["highlight_outreach_reason"] = None
    app.render_mail_gateway_ui()
