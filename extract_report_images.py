"""
One-time migration script: extracts the base64 report-image constants
(Q1_P1, Q2_P1, Q2_P2, Q2_P3, PBR_P1, PBD_P1-5, SES_P1-5, and the *_PAGES
list constants) out of app.py and into a standalone module,
data/seed/report_images.py, with zero Streamlit dependency.

Why this is needed: reports_page.py (NiceGUI) does `import app` to reach
these constants, but the real app.py has `st.set_page_config(...)` and all
its page-routing logic sitting at module level (not inside a function) —
so a plain `import app` doesn't just grab the constants, it tries to
execute the entire ~12,750-line Streamlit script as a side effect
(accessing st.session_state, st.sidebar, etc. outside a running Streamlit
session), which is why the Reports page renders blank in the NiceGUI app.

This script only COPIES the constant lines — app.py is left completely
unchanged, so `streamlit run app.py` keeps working exactly as before.

Run once:  python extract_report_images.py
Safe to re-run — it always overwrites data/seed/report_images.py fresh
from whatever is currently in app.py.
"""

import os

SOURCE = "app.py"
DEST = os.path.join("data", "seed", "report_images.py")

# 1-indexed line numbers in app.py holding each constant's definition
# (each constant is exactly one line: NAME = "<base64 string>").
LINE_NUMBERS = {
    44: "Q1_P1",
    45: "Q2_P1",
    46: "Q2_P2",
    47: "Q2_P3",
    449: "PBR_P1",
    450: "PBR_PAGES",
    451: "PBD_P1",
    452: "PBD_P2",
    453: "PBD_P3",
    454: "PBD_P4",
    455: "PBD_P5",
    456: "PBD_PAGES",
    457: "SES_P1",
    458: "SES_P2",
    459: "SES_P3",
    460: "SES_P4",
    461: "SES_P5",
    462: "SES_PAGES",
}


def main():
    with open(SOURCE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    os.makedirs(os.path.dirname(DEST), exist_ok=True)

    missing = []
    extracted = {}
    for lineno, name in LINE_NUMBERS.items():
        idx = lineno - 1
        if idx >= len(lines):
            missing.append((lineno, name))
            continue
        line = lines[idx].rstrip("\n")
        if not line.strip().startswith(name):
            missing.append((lineno, name))
            continue
        extracted[name] = line

    if missing:
        print("WARNING — app.py's line numbers have shifted since this script was written.")
        print("Could not confirm these constants at their expected line:")
        for lineno, name in missing:
            print(f"  line {lineno}: expected to start with '{name}'")
        print("\nNothing was written. Re-run with updated line numbers, or extract these by hand.")
        return

    header = (
        '"""\n'
        "data/seed/report_images.py — base64-encoded report page images,\n"
        "extracted from app.py (see extract_report_images.py at the project\n"
        "root for how/why). No Streamlit dependency, so reports_page.py can\n"
        "import these directly without pulling in app.py's Streamlit runtime.\n"
        '"""\n\n'
    )

    with open(DEST, "w", encoding="utf-8") as f:
        f.write(header)
        # Write in the same order as LINE_NUMBERS (source order), individual
        # image constants first, *_PAGES list constants immediately after
        # the images they reference — matches app.py's own layout.
        for name in ["Q1_P1", "Q2_P1", "Q2_P2", "Q2_P3",
                     "PBR_P1", "PBR_PAGES",
                     "PBD_P1", "PBD_P2", "PBD_P3", "PBD_P4", "PBD_P5", "PBD_PAGES",
                     "SES_P1", "SES_P2", "SES_P3", "SES_P4", "SES_P5", "SES_PAGES"]:
            f.write(extracted[name] + "\n")

    print(f"Wrote {len(extracted)} constants to {DEST}")
    print("app.py was NOT modified.")
    print("\nNext: reports_page.py needs to import from data.seed.report_images")
    print("instead of `import app` — Claude will make that edit next.")


if __name__ == "__main__":
    main()
