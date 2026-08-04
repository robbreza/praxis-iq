#!/usr/bin/env python3
"""scripts/sync_roadmap.py — mirror the working roadmap memory into docs/ROADMAP.md.

The near-term roadmap / session log lives in Claude's persistent memory
(`praxis-next-steps`). This regenerates the in-repo, version-controlled copy so the
plan is visible to anyone with the repo, not only inside Claude. Run it after the
roadmap memory changes, then commit docs/ROADMAP.md.

    python scripts/sync_roadmap.py            # use the default memory path
    python scripts/sync_roadmap.py <path>     # or point at the memory .md explicitly
    PRAXIS_ROADMAP_MEMORY=<path> python scripts/sync_roadmap.py

It strips the memory's YAML frontmatter, prepends a doc header stamped with today's
date, and writes docs/ROADMAP.md. Exits 0 whether or not the content changed (it
prints which).
"""
import os
import sys
from datetime import date

# Default location of the roadmap memory on this workstation. Override via argv[1]
# or the PRAXIS_ROADMAP_MEMORY env var if the memory dir ever moves.
DEFAULT_MEMORY = (
    r"C:\Users\Owner\.claude\projects\C--Users-Owner\memory\praxis-next-steps.md"
)

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_OUT = os.path.join(_REPO_ROOT, "docs", "ROADMAP.md")


def _strip_frontmatter(text):
    """Drop a leading '--- ... ---' YAML block, if present."""
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[end + 4:].lstrip("\n")
    return text


def main():
    mem_path = (
        (sys.argv[1] if len(sys.argv) > 1 else None)
        or os.environ.get("PRAXIS_ROADMAP_MEMORY")
        or DEFAULT_MEMORY
    )
    if not os.path.exists(mem_path):
        print(f"ERROR: roadmap memory not found: {mem_path}", file=sys.stderr)
        print("Pass the path as an argument or set PRAXIS_ROADMAP_MEMORY.", file=sys.stderr)
        return 2

    body = _strip_frontmatter(open(mem_path, encoding="utf-8").read())
    header = (
        "# Praxis Point IR — Roadmap & Session Notes\n\n"
        "> Mirrored from the working roadmap memory (`praxis-next-steps`) by "
        "`scripts/sync_roadmap.py`.\n"
        "> Near-term roadmap for the Praxis Point IR platform after the 2026-07-15 demo. "
        "Entries are\n"
        "> reverse-chronological (newest first). `[[name]]` markers reference related "
        "working-memory notes.\n"
        ">\n"
        f"> _Last synced from memory: {date.today():%Y-%m-%d}._\n\n"
        "---\n\n"
    )
    new_content = header + body

    old_content = open(_OUT, encoding="utf-8").read() if os.path.exists(_OUT) else None
    os.makedirs(os.path.dirname(_OUT), exist_ok=True)
    open(_OUT, "w", encoding="utf-8").write(new_content)

    rel = os.path.relpath(_OUT, _REPO_ROOT)
    if old_content == new_content:
        print(f"{rel} already up to date ({sum(1 for _ in new_content.splitlines())} lines).")
    else:
        print(f"Synced {rel} from {mem_path} "
              f"({sum(1 for _ in new_content.splitlines())} lines). Commit it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
