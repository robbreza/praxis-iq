"""
config/theme_tokens.py — clean semantic design tokens, shared by both the
legacy Streamlit app (app.py, via config/theme.py's CSS_TEMPLATE) and the
new NiceGUI app (app_nicegui.py and everything under page_modules_nicegui/).

This is the single source of truth for color decisions going forward. The
values below match config/theme.py's DARK_THEME and CREAM_THEME exactly —
same colors, just organized as a plain dict instead of a CSS find/replace
map, since NiceGUI doesn't need CSS text substitution the way the old
Streamlit override hack did.

DARK is the current, live look. CREAM is the draft warm/purple palette from
HANDOFF.md's design direction — still not activated (see ACTIVE below),
still needs a human to eyeball it live before it ships.
"""

DARK = {
    "canvas_bg":       "#0F172A",
    "sidebar_bg":      "#131E2E",
    "surface_bg":      "#1E293B",
    "surface_hover_bg":"#253347",
    "border":          "#334155",
    "accent":          "#3B82F6",
    "accent_strong":   "#1D4ED8",
    "accent_strong_hover": "#2563EB",
    "accent_light":    "#60A5FA",
    "accent_light2":   "#93C5FD",
    "text_body":       "#E2E8F0",
    "text_heading":    "#F1F5F9",
    "text_secondary":  "#CBD5E1",
    "text_muted":      "#94A3B8",
    "text_muted2":     "#64748B",
    # Semantic status colors — same in both themes, see config/theme.py's
    # docstring for why these deliberately don't change with the palette.
    "positive":        "#6BCB77",
    "negative":        "#FF8080",
    "warning":         "#F59E0B",
    "danger":          "#EF4444",
    "success":         "#22C55E",
}

CREAM = {
    "canvas_bg":       "#FAF7F2",
    "sidebar_bg":      "#F1EAE0",
    "surface_bg":      "#FFFFFF",
    "surface_hover_bg":"#F3ECE0",
    "border":          "#E3D9C6",
    "accent":          "#6D5BD0",
    "accent_strong":   "#5B4BC4",
    "accent_strong_hover": "#4E3FB0",
    "accent_light":    "#8677D9",
    "accent_light2":   "#B3A8E8",
    "text_body":       "#3A362E",
    "text_heading":    "#211D17",
    "text_secondary":  "#57503F",
    "text_muted":      "#8A8272",
    "text_muted2":     "#948C7A",
    "positive":        "#2E7559",
    "negative":        "#BA2D2D",
    "warning":         "#F59E0B",
    "danger":          "#EF4444",
    "success":         "#22C55E",
}

# INSTITUTIONAL — cool "institutional finance" palette (slate neutrals + a
# deep indigo/navy accent), the FactSet / Capital IQ light register. Chosen
# 2026-07-13 (over CREAM) for the CFO demo: more conventional/trustworthy for
# a traditional finance exec, and every text color here clears WCAG AA on its
# background — the muted floor is slate-600 #475569 (~7:1) / slate-500 #64748B
# (~4.6:1), fixing CREAM's #8A8272 muted taupe that failed at ~2.6:1. Lightest
# slate (#94A3B8) is reserved for NON-text (dividers, disabled) only.
INSTITUTIONAL = {
    "canvas_bg":       "#F4F6F9",
    "sidebar_bg":      "#EAEEF3",
    "surface_bg":      "#FFFFFF",
    "surface_hover_bg":"#EEF2F7",
    "border":          "#D3DBE4",
    "accent":          "#1E40AF",   # indigo-800 — primary accent / buttons
    "accent_strong":   "#1E3A8A",   # navy — active nav, emphasis
    "accent_strong_hover": "#182F6E",
    "accent_light":    "#3B5BC4",   # accent text/icons on light (>=4.5:1)
    "accent_light2":   "#5B7BD6",   # subtle highlights (non-critical text)
    "text_body":       "#1E293B",   # slate-800  (~13:1 on white)
    "text_heading":    "#0F172A",   # slate-900  (~16:1)
    "text_secondary":  "#475569",   # slate-600  (~7:1) — muted floor for text
    "text_muted":      "#64748B",   # slate-500  (~4.6:1) — passes AA
    "text_muted2":     "#94A3B8",   # slate-400  — NON-text only (dividers)
    "positive":        "#15803D",   # green-700
    "negative":        "#B91C1C",   # red-700
    "warning":         "#B45309",   # amber-700
    "danger":          "#B91C1C",   # red-700
    "success":         "#15803D",   # green-700
}

# Was CREAM (2026-07-08); switched to INSTITUTIONAL per user review 2026-07-13.
ACTIVE = INSTITUTIONAL
