"""
config/theme.py — design tokens (colors, fonts, spacing) for the Praxis Point
IR platform, pulled out of the inline CSS block that used to live directly in
app.py (~550 lines, st.markdown("""<style>...</style>""") around what was
originally lines 822-1100+ of the single-file demo).

--- Two themes exist here ---
DARK_THEME is the CURRENT, LIVE look (the dark navy/blue theme users see
today). ACTIVE_THEME points at DARK_THEME by default, so extracting this
file causes ZERO visual change — this step is a structural move only.

CREAM_THEME is a DRAFT of the new look HANDOFF.md's design direction asked
for: "warm off-white/cream canvas, graphite body text, a single confident
purple/indigo accent, soft rounded cards with thin borders, clean uppercase
micro-labels, generous whitespace." It is a systematic color remap of the
exact same CSS structure (every dark-theme hex value swapped for a cream-
theme one), not a redesign from scratch — no selectors, layout, or spacing
changed, only color values.

CREAM_THEME has NOT been turned on yet (see ACTIVE_THEME below). It should
be reviewed live in the running app before flipping the switch — a color
palette is much easier to sanity-check by eye on a real screen than by
reading hex codes, and this file's author (an AI assistant) has no way to
render a preview from its side to catch a bad contrast pairing before a
person sees it. Flip it by changing ACTIVE_THEME to CREAM_THEME below once
reviewed.

Semantic status colors (positive/negative tags, badge-active/pending,
signal-red/amber/green/blue chips, brief-item urgent/warning/good borders)
are deliberately left the SAME in both themes — green-means-good and
red-means-bad conventions don't need to change just because the background
did, and changing them wasn't part of what HANDOFF.md's design brief asked
for.
"""

DARK_THEME = "dark"
CREAM_THEME = "cream"

# ── Flip this to CREAM_THEME once the draft palette has been reviewed live ──
ACTIVE_THEME = DARK_THEME


# Maps every structural (non-semantic-status) color in the CSS template from
# its current dark-theme hex/rgba value to its draft cream-theme replacement.
# Applied as plain text substitution over CSS_TEMPLATE — see get_theme_css().
_CREAM_COLOR_MAP = {
    # ── Canvas / surface layers ──
    "#0F172A": "#FAF7F2",   # base canvas: dark navy -> warm off-white/cream
    "#131E2E": "#F1EAE0",   # sidebar: slightly deeper cream than base canvas
    "#1E293B": "#FFFFFF",   # cards/tables/inputs (Layer 2): pure white on cream
    "#253347": "#F3ECE0",   # hover / input-focus surfaces (Layer 3)

    # ── Borders ──
    "#334155": "#E3D9C6",   # thin warm border, replacing cool slate border

    # ── Primary accent (blue -> purple/indigo) ──
    "#3B82F6": "#6D5BD0",   # primary accent
    "#1D4ED8": "#5B4BC4",   # accent strong (primary button bg, accent card border)
    "#2563EB": "#4E3FB0",   # accent strong hover
    "#60A5FA": "#8677D9",   # accent light (links, icons, caret, dropdown arrow)
    "#93C5FD": "#B3A8E8",   # accent light 2
    "rgba(59,130,246,0.08)": "rgba(109,91,208,0.08)",  # active-tab underline glow

    # ── Text ──
    "#E2E8F0": "#3A362E",   # body text: light-on-dark -> graphite-on-cream
    "#F1F5F9": "#211D17",   # heading text: near-white -> dark graphite
    "#CBD5E1": "#57503F",   # secondary text (labels, nav items)
    "#94A3B8": "#8A8272",   # muted text (captions, metric labels)
    "#8B9DB8": "#8A8272",   # section-eyebrow muted label
    "#64748B": "#948C7A",   # placeholder text / secondary muted
}


# The exact CSS previously inline in app.py's st.markdown("""<style>...) call.
# DARK_THEME uses this verbatim (byte-identical to the original demo).
CSS_TEMPLATE = """
<style>
/* ── HIDE DEFAULT STREAMLIT ELEMENTS ── */
#MainMenu {visibility:hidden;}
footer    {visibility:hidden;}
header    {visibility:hidden;}
[data-testid="stSidebar"] > div:first-child {padding-top:0;}

/* ── GLOBAL RIGHT-SIDE BREATHING ROOM — half an inch, applied once here
   rather than patched into every individual section. Everything in the
   main content area was running flush to the right edge, forcing the eye
   to travel the full width on every line. ── */
[data-testid="stAppViewContainer"] .main .block-container {
    padding-right: 48px !important;
}

/* ══ PHASE 1: CANVAS — elevation system ══
   Layer 0 (base canvas):   #0F172A  ← ultra-dark neutral-blue, no chromatic aberration
   Layer 1 (sidebar):       #131E2E  ← slightly lighter
   Layer 2 (cards/tables):  #1E293B  ← distinctly lighter, clear depth
   Layer 3 (inputs/rows):   #253347  ← hover/input surfaces
   Accent border:           #334155
   Primary accent:          #3B82F6  ← blue that reads cleanly on dark
*/

/* ── BASE ── */
html, body, [data-testid="stAppViewContainer"] {
    background: #0F172A;
    color: #E2E8F0;
    font-family: 'Inter', 'SF Pro Display', -apple-system, sans-serif;
    font-size: 14px;
    line-height: 1.5;
}



/* ── MAIN CONTENT ── */
[data-testid="stMainBlockContainer"] {
    background: #0F172A;
    padding: 0 !important;
}

/* ── SIDEBAR ── */
[data-testid="stSidebar"] {
    background: #131E2E !important;
    border-right: 1px solid #1E293B;
    min-width: 224px !important;
    max-width: 224px !important;
    padding-left: 0 !important;
}

/* ══ PHASE 2: TYPOGRAPHY SCALE ══
   Page title:       24px / 700
   Section header:   20px / 600
   Table col header: 12px / 500  uppercase  letter-spacing .05em
   Table body:       14px / 400–500
   Caption/meta:     12px / 400  muted
*/

/* Headings — targeted, no side effects */
h1, h2, h3 { color: #F1F5F9; }
h2 { font-size: 24px; font-weight: 700; margin-bottom: 4px; }
h3 { font-size: 20px; font-weight: 600; }
h4 { font-size: 16px; font-weight: 600; color: #E2E8F0; }

/* Streamlit markdown heading override — only what's needed */
[data-testid="stMarkdownContainer"] h4 { color: #F1F5F9 !important; font-size: 17px !important; font-weight: 700 !important; }
[data-testid="stMarkdownContainer"] h3 { color: #F1F5F9 !important; }
[data-testid="stMarkdownContainer"] h2 { color: #F1F5F9 !important; }
.stMarkdown p, .stMarkdown li { color: #E2E8F0; line-height: 1.6; }

/* Section label above headings — muted per design review: too bright at #60A5FA, was
   competing with body content instead of receding as a label should */
.section-eyebrow {
    font-size: 11px;
    color: #8B9DB8;
    text-transform: uppercase;
    letter-spacing: .10em;
    font-weight: 500;
    margin-bottom: 4px;
}
.section-title   { font-size: 20px; font-weight: 700; color: #F1F5F9; margin-bottom: 16px; }
.section-divider { border: none; border-top: 1px solid #1E293B; margin: 16px 0; }

/* Status pills — replace bare colored text (low contrast on dark blue backgrounds)
   with background pills, per design review */
.positive-tag {
    background-color: rgba(46, 117, 89, 0.22);
    color: #6BCB77;
    padding: 3px 10px;
    border-radius: 4px;
    font-weight: 700;
    font-size: 0.95em;
}
.negative-tag {
    background-color: rgba(186, 45, 45, 0.22);
    color: #FF8080;
    padding: 3px 10px;
    border-radius: 4px;
    font-weight: 700;
    font-size: 0.95em;
}

/* Scoped serif treatment for the two primary editorial headers only (greeting,
   "Today's Story") — deliberately NOT applied globally. Streamlit's theme-level
   font setting is all-or-nothing (buttons, tables, numbers included), which would
   work against the "keep data in a clean geometric sans" half of the same request. */
.exec-serif {
    font-family: Georgia, 'Times New Roman', serif;
}

/* Small sharp status dot — replacement for emoji indicators, which render
   inconsistently across OS/browser and read as less "institutional" */
.status-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    margin-right: 6px;
    vertical-align: middle;
}

/* Native st.container(border=True) — styled to match .ir-card exactly, so it can be
   used wherever a section needs to visually align its edges with the custom HTML
   cards elsewhere on the page (mixing raw HTML and native widgets inside one HTML
   div doesn't render correctly in Streamlit — this is the supported way to do it) */
[data-testid="stVerticalBlockBorderWrapper"] {
    border-color: #334155 !important;
    border-radius: 12px !important;
}

/* ══ PHASE 3: COMPONENTS ══ */

/* ── CARDS — elevated surface ── */
.ir-card {
    background: #1E293B;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 16px;
}
.ir-card-accent {
    background: #1E293B;
    border: 1px solid #1D4ED8;
    border-left: 3px solid #3B82F6;
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 16px;
}

/* ── SIDEBAR NAV — left-border accent, no jarring white flash ── */
.nav-section {
    font-size: 11px;
    color: #CBD5E1;
    text-transform: uppercase;
    letter-spacing: .08em;
    padding: 16px 16px 6px;
    font-weight: 700;
}
.nav-item {
    display: flex; align-items: center; gap: 10px;
    padding: 8px 12px 8px 14px;
    border-radius: 6px;
    margin: 1px 8px;
    cursor: pointer;
    font-size: 14px;
    color: #E2E8F0;
    font-weight: 500;
    transition: all .12s;
    border-left: 3px solid transparent;
}
.nav-item:hover { background: #1E293B; color: #E2E8F0; }
.nav-item.active {
    background: #1E293B;
    color: #F1F5F9;
    border-left: 3px solid #3B82F6;
    font-weight: 600;
}
/* Sidebar nav buttons — two-line support */
[data-testid="stSidebar"] .stButton {
    padding: 0 12px !important;
}
[data-testid="stSidebar"] .stButton > button {
    white-space: pre-line !important;
    line-height: 1.4 !important;
    min-height: 48px !important;
    height: auto !important;
    padding: 10px 14px !important;
    text-align: left !important;
    font-size: 14px !important;
}
[data-testid="stSidebar"] .stButton > button[kind="primary"] {
    background: #1E3A5F !important;
    border-color: #3B82F6 !important;
    color: #F1F5F9 !important;
    border-left: 3px solid #3B82F6 !important;
}

/* ── STREAMLIT BUTTON OVERRIDES — consistent with design ── */
/* Covers both the classic .stButton wrapper AND st.popover's trigger button
   (a different internal component that doesn't get wrapped in .stButton),
   plus modern Streamlit's data-testid-based button variants — some buttons
   (the "On Your Calendar" cards, Investor Pipeline popover rows, analyst
   arrow buttons) were falling through to Streamlit's default light-theme
   button style because only .stButton was targeted before. */
.stButton > button,
.stDownloadButton > button,
[data-testid="stPopover"] button,
button[data-testid^="stBaseButton"] {
    background: #1E293B !important;
    color: #CBD5E1 !important;
    border: 1px solid #334155 !important;
    border-radius: 8px !important;
    font-size: 15px !important;
    font-weight: 500 !important;
    padding: 6px 16px !important;
    transition: all .15s !important;
}
.stButton > button *,
.stDownloadButton > button *,
[data-testid="stPopover"] button *,
button[data-testid^="stBaseButton"] * {
    color: inherit !important;
}
.stButton > button:hover,
.stDownloadButton > button:hover,
[data-testid="stPopover"] button:hover,
button[data-testid^="stBaseButton"]:hover {
    background: #253347 !important;
    border-color: #3B82F6 !important;
    color: #F1F5F9 !important;
}
.stButton > button[kind="primary"],
button[data-testid="stBaseButton-primary"] {
    background: #1D4ED8 !important;
    border-color: #3B82F6 !important;
    color: #F1F5F9 !important;
    font-weight: 600 !important;
}
.stButton > button[kind="primary"]:hover,
button[data-testid="stBaseButton-primary"]:hover {
    background: #2563EB !important;
}

/* ── TABS — larger, cleaner active state ── */
.stTabs [data-baseweb="tab-list"] {
    background: #131E2E;
    border-bottom: 1px solid #334155;
    gap: 0;
}
.stTabs [data-baseweb="tab"] {
    color: #94A3B8;
    background: transparent;
    border: none;
    padding: 12px 20px;
    font-size: 14px;
    font-weight: 500;
    transition: color .12s;
}
.stTabs [data-baseweb="tab"]:hover { color: #CBD5E1; }
.stTabs [aria-selected="true"] {
    color: #FFFFFF !important;
    font-weight: 700 !important;
    border-bottom: 3px solid #60A5FA !important;
    background: rgba(59,130,246,0.08) !important;
}

/* ── INPUTS — COMPREHENSIVE FIX ──
   Root cause: container colors don't affect typed text.
   Must target the actual input/textarea elements directly.
   Design system: bg #1E293B, text #E2E8F0, border #334155
*/

/* All input containers */
.stSelectbox > div, .stTextInput > div > div,
.stMultiSelect > div {
    background: #1E293B !important;
    border-color: #334155 !important;
}

/* THE CRITICAL FIX — actual typed text in every input type */
.stTextInput input,
.stTextInput > div > div > input,
div[data-testid="stTextInput"] input,
input[class*="st-"] {
    background: #1E293B !important;
    color: #E2E8F0 !important;
    font-size: 15px !important;
    caret-color: #60A5FA !important;
    border-color: #334155 !important;
}

/* Placeholder text — visible but muted */
.stTextInput input::placeholder,
div[data-testid="stTextInput"] input::placeholder,
input[class*="st-"]::placeholder {
    color: #64748B !important;
    opacity: 1 !important;
}

/* Text area typed text */
.stTextArea textarea,
div[data-testid="stTextArea"] textarea {
    background: #1E293B !important;
    color: #E2E8F0 !important;
    font-size: 15px !important;
    border-color: #334155 !important;
    caret-color: #60A5FA !important;
}
.stTextArea textarea::placeholder,
div[data-testid="stTextArea"] textarea::placeholder {
    color: #64748B !important;
    opacity: 1 !important;
}

/* Selectbox — full override including dropdown arrow */
.stSelectbox [data-baseweb="select"],
div[data-testid="stSelectbox"] [data-baseweb="select"] {
    background: #1E293B !important;
    border: 1px solid #334155 !important;
    border-radius: 8px !important;
}
.stSelectbox [data-baseweb="select"] > div,
div[data-testid="stSelectbox"] [data-baseweb="select"] > div {
    background: #1E293B !important;
    color: #E2E8F0 !important;
    font-size: 15px !important;
}
/* Dropdown arrow — always visible */
.stSelectbox [data-baseweb="select"] svg,
div[data-testid="stSelectbox"] [data-baseweb="select"] svg,
div[data-testid="stSelectbox"] svg {
    fill: #60A5FA !important;
    color: #60A5FA !important;
    opacity: 1 !important;
    display: block !important;
    visibility: visible !important;
    width: 20px !important;
    height: 20px !important;
}
/* The chevron container */
div[data-testid="stSelectbox"] [data-baseweb="select"] [data-id="chevron-down"],
.stSelectbox [aria-hidden="true"] {
    display: flex !important;
    align-items: center !important;
    opacity: 1 !important;
    color: #60A5FA !important;
}
/* Selected value text */
div[data-testid="stSelectbox"] [data-baseweb="select"] span {
    color: #E2E8F0 !important;
    font-size: 15px !important;
}
/* Hover state */
div[data-testid="stSelectbox"] [data-baseweb="select"]:hover {
    border-color: #3B82F6 !important;
}

/* Selectbox dropdown options */
[data-baseweb="popover"] [role="option"],
[data-baseweb="menu"] [role="option"] {
    background: #1E293B !important;
    color: #E2E8F0 !important;
    font-size: 15px !important;
}
[data-baseweb="popover"] [role="option"]:hover,
[data-baseweb="menu"] [role="option"]:hover {
    background: #253347 !important;
    color: #F1F5F9 !important;
}

/* st.popover body content renders on a white surface regardless of the app's
   dark theme — our global light-grey text color (meant for the dark canvas)
   was carrying over and reading as low-contrast grey-on-white. Force dark text
   inside popover content specifically, keep the white background as-is. */
[data-testid="stPopoverBody"],
[data-baseweb="popover"] [data-testid="stVerticalBlock"] {
    background: #FFFFFF;
}
[data-testid="stPopoverBody"] p,
[data-testid="stPopoverBody"] span,
[data-testid="stPopoverBody"] div,
[data-testid="stPopoverBody"] li,
[data-testid="stPopoverBody"] label,
[data-testid="stPopoverBody"] .stMarkdown {
    color: #111827 !important;
}
[data-testid="stPopoverBody"] [data-testid="stCaptionContainer"],
[data-testid="stPopoverBody"] [data-testid="stCaptionContainer"] p {
    color: #4B5563 !important;
}

/* ALL labels — every widget type */
.stSelectbox label, .stTextInput label, .stTextArea label,
.stNumberInput label, .stFileUploader label, .stRadio label,
.stCheckbox label, .stSlider label, .stMultiSelect label,
div[data-testid="stWidgetLabel"] p,
div[data-testid="stWidgetLabel"] label {
    color: #E2E8F0 !important;
    font-size: 15px !important;
    font-weight: 500 !important;
}

/* Focus state — blue border glow */
.stTextInput input:focus,
.stTextArea textarea:focus {
    border-color: #3B82F6 !important;
    box-shadow: 0 0 0 2px rgba(59,130,246,0.25) !important;
    outline: none !important;
}
.stMarkdown p, .stMarkdown li { color: #E2E8F0; line-height: 1.6; }
/* Streamlit's markdown parser auto-links bare emails/URLs (e.g. inside
   st.caption() text) into unstyled <a> tags, which inherit a low-contrast
   default link color against this dark theme — root cause of several
   "can barely read this" reports. Only targets links WITHOUT an explicit
   inline style, so custom-styled buttons (like mailto_link()'s output,
   which always carries a style attribute) are untouched. */
.stMarkdown a:not([style]), .stCaption a:not([style]),
[data-testid="stCaptionContainer"] a:not([style]),
[data-testid="stMarkdownContainer"] a:not([style]) {
    color: #60A5FA !important;
    text-decoration: underline;
}
.stCaption p, [data-testid="stCaptionContainer"] p {
    color: #94A3B8 !important;
    font-size: 14px !important;
}
div[data-testid="stForm"] label { color: #CBD5E1 !important; font-size: 15px !important; }
/* Radio button — ALL text elements bright and readable */
.element-container .stRadio > label { color: #E2E8F0 !important; font-size: 16px !important; font-weight: 600 !important; }
.element-container .stRadio [data-testid="stWidgetLabel"] { color: #E2E8F0 !important; font-size: 16px !important; }
.stRadio [data-testid="stMarkdownContainer"] p { color: #E2E8F0 !important; font-size: 16px !important; font-weight: 500 !important; }
.stRadio div[role="radiogroup"] label { color: #E2E8F0 !important; font-size: 16px !important; }
.stRadio div[role="radiogroup"] p { color: #E2E8F0 !important; font-size: 16px !important; }
[data-testid="stWidgetLabel"] { color: #E2E8F0 !important; font-size: 16px !important; }
[data-testid="stWidgetLabel"] p { color: #E2E8F0 !important; font-size: 16px !important; }
/* Selectbox, checkbox, all widget labels */
.stCheckbox [data-testid="stMarkdownContainer"] p { color: #E2E8F0 !important; font-size: 15px !important; }
.stCheckbox label { color: #E2E8F0 !important; font-size: 15px !important; }
.stNumberInput > div > div {
    background: #1E293B !important;
    border: 1px solid #334155 !important;
    border-radius: 8px !important;
}
.stNumberInput input { background: #1E293B !important; color: #F1F5F9 !important; font-weight: 600 !important; }
.stNumberInput button { background: #253347 !important; border-color: #334155 !important; color: #60A5FA !important; }
.stNumberInput button:hover { background: #2D4A6A !important; color: #F1F5F9 !important; }
.stNumberInput label { color: #CBD5E1 !important; }
/* stTextArea — covered in comprehensive inputs block above */

/* ── METRICS ── */
.stMetric { background: #1E293B; border: 1px solid #334155; border-radius: 10px; padding: 16px 20px !important; }
.stMetric [data-testid="metric-container"] { background: transparent !important; }
.stMetric label { color: #94A3B8 !important; font-size: 15px !important; text-transform: uppercase; letter-spacing: .04em; }
.stMetric [data-testid="stMetricValue"] { color: #F1F5F9 !important; font-size: 22px !important; font-weight: 700 !important; }

/* ── FORMS / EXPANDERS / DATAFRAMES ── */
div[data-testid="stForm"] { background: #1E293B; border: 1px solid #334155; border-radius: 12px; padding: 20px; }
.stExpander { background: #1E293B; border: 1px solid #334155; border-radius: 10px; }
.stExpander header { color: #CBD5E1 !important; font-size: 14px !important; }
.stDataFrame { background: #1E293B; border-radius: 8px; }
[data-testid="stAlert"] { border-radius: 10px; }

/* ── STATUS BADGES — pill-shaped, low-opacity background ── */
.badge-active {
    display: inline-flex; align-items: center; gap: 5px;
    background: rgba(34,197,94,0.12);
    color: #4ADE80;
    border: 1px solid rgba(74,222,128,0.3);
    padding: 3px 10px;
    border-radius: 999px;
    font-size: 14px;
    font-weight: 600;
}
.badge-active::before { content: '●'; font-size: 8px; }
.badge-pending {
    display: inline-flex; align-items: center; gap: 5px;
    background: rgba(100,116,139,0.15);
    color: #CBD5E1;
    border: 1px solid rgba(100,116,139,0.25);
    padding: 3px 10px;
    border-radius: 999px;
    font-size: 14px;
    font-weight: 500;
}
.badge-pending::before { content: '○'; font-size: 8px; }

/* ── TABLES — structured, readable ── */
.ir-table { width: 100%; border-collapse: collapse; font-size: 14px; }
.ir-table th {
    padding: 10px 16px;
    text-align: left;
    font-size: 14px;
    font-weight: 500;
    color: #CBD5E1;
    text-transform: uppercase;
    letter-spacing: .05em;
    border-bottom: 1px solid #334155;
    background: #1E293B;
}
.ir-table th:last-child { text-align: right; }
.ir-table td {
    padding: 12px 16px;
    border-bottom: 1px solid #1E293B;
    color: #E2E8F0;
    font-size: 14px;
}
.ir-table td:last-child { text-align: right; }
.ir-table tr:hover td { background: #253347; }

/* ── BRIEF / SIGNAL ITEMS ── */
.brief-item {
    background: #1E293B;
    border-left: 3px solid #3B82F6;
    border-radius: 0 8px 8px 0;
    padding: 12px 16px;
    margin-bottom: 8px;
}
.brief-item.urgent  { border-left-color: #EF4444; }
.brief-item.warning { border-left-color: #F59E0B; }
.brief-item.good    { border-left-color: #22C55E; }
.brief-item .item-label  { font-size: 15px; color: #CBD5E1; text-transform: uppercase; letter-spacing: .08em; }
.brief-item .item-text   { font-size: 14px; color: #CBD5E1; margin-top: 3px; line-height: 1.4; }
.brief-item .item-action { font-size: 14px; color: #60A5FA; margin-top: 4px; font-weight: 500; }

/* ── SIGNAL CHIPS ── */
.signal-red   { background:rgba(239,68,68,.12);  border:1px solid rgba(239,68,68,.3);  color:#FCA5A5; padding:5px 12px; border-radius:20px; font-size:12px; font-weight:600; display:inline-block; margin:3px; }
.signal-amber { background:rgba(245,158,11,.12); border:1px solid rgba(245,158,11,.3); color:#FCD34D; padding:5px 12px; border-radius:20px; font-size:12px; font-weight:600; display:inline-block; margin:3px; }
.signal-green { background:rgba(34,197,94,.12);  border:1px solid rgba(34,197,94,.3);  color:#86EFAC; padding:5px 12px; border-radius:20px; font-size:12px; font-weight:600; display:inline-block; margin:3px; }
.signal-blue  { background:rgba(59,130,246,.12); border:1px solid rgba(59,130,246,.3); color:#93C5FD; padding:5px 12px; border-radius:20px; font-size:12px; font-weight:600; display:inline-block; margin:3px; }

/* ── METRIC TILES ── */
.metric-tile { background:#1E293B; border:1px solid #334155; border-radius:10px; padding:16px 18px; text-align:center; }
.metric-tile .val { font-size:28px; font-weight:700; color:#F1F5F9; line-height:1.1; }
.metric-tile .lbl { font-size:13px; color:#94A3B8; text-transform:uppercase; letter-spacing:.08em; margin-top:4px; }
.metric-tile .sub { font-size:12px; color:#94A3B8; margin-top:2px; }

/* ── WORKFLOW / STAGE ── */
.stage-pill { display:inline-flex; align-items:center; gap:8px; background:#1E293B; border:1px solid #334155; border-radius:24px; padding:6px 14px; font-size:12px; color:#CBD5E1; }
.stage-dot  { width:8px; height:8px; border-radius:50%; display:inline-block; }

/* ── COUNTDOWN ── */
.countdown-ring  { background:conic-gradient(#3B82F6 calc(var(--pct)*1%),#1E293B 0); border-radius:50%; width:72px; height:72px; display:flex; align-items:center; justify-content:center; margin:0 auto; }
.countdown-inner { background:#0F172A; border-radius:50%; width:56px; height:56px; display:flex; flex-direction:column; align-items:center; justify-content:center; }

/* ── LIVE FEED ── */
.live-item      { border-bottom:1px solid #1E293B; padding:10px 0; }
.live-item .live-time { font-size:12px; color:#94A3B8; }
.live-item .live-text { font-size:13px; color:#94A3B8; margin-top:2px; }
</style>
"""


def get_theme_css(theme=None):
    """Returns the full <style>...</style> block for the given theme name
    (DARK_THEME or CREAM_THEME), or ACTIVE_THEME if not specified. Pass the
    result straight to st.markdown(..., unsafe_allow_html=True)."""
    theme = theme or ACTIVE_THEME
    css = CSS_TEMPLATE
    if theme == CREAM_THEME:
        for old, new in _CREAM_COLOR_MAP.items():
            css = css.replace(old, new)
    return css


def render_global_css(theme=None):
    """Convenience wrapper so app.py's call site reads like the original
    st.markdown("""...<style>...""", unsafe_allow_html=True) call, just
    sourced from here instead of an inline triple-quoted string."""
    import streamlit as st
    st.markdown(get_theme_css(theme), unsafe_allow_html=True)
