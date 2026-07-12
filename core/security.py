"""
core/security.py — secrets loading. No literals, ever.

Loads environment variables from a local .env file (via python-dotenv) and
verifies ANTHROPIC_API_KEY is present before the app relies on it. This is
the ONLY place that should read ANTHROPIC_API_KEY (or any future secret) —
every other module should get secrets by importing from here, never by
reading os.environ directly or hardcoding a value.

History: the original single-file demo had a live Anthropic API key
hardcoded in 3 places in app.py. That key was removed and revoked. Do not
reintroduce a hardcoded key anywhere in this codebase, including in
comments, test files, or commit history.
"""

import os
import sys

_loaded = False


def load_environment():
    """Load .env (if python-dotenv is installed and a .env file exists) and
    warn loudly — but do not crash — if ANTHROPIC_API_KEY is still missing
    afterward. Safe to call more than once; only loads once per process."""
    global _loaded
    if _loaded:
        return
    _loaded = True

    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "ERROR: ANTHROPIC_API_KEY is not set. Create a .env file "
            "(copy .env.example to .env in the project root) with "
            "ANTHROPIC_API_KEY=your-key-here.",
            file=sys.stderr,
        )


def get_anthropic_api_key():
    """The one sanctioned way to read the Anthropic API key. Returns None
    if it isn't set — callers should handle that case explicitly rather
    than assuming a key is always present."""
    load_environment()
    return os.environ.get("ANTHROPIC_API_KEY")


def get_database_url():
    """The one sanctioned way to read the Neon Postgres connection string
    (DATABASE_URL in .env — Neon dashboard -> project -> Connection
    Details). Unlike ANTHROPIC_API_KEY, this is optional and deliberately
    silent when missing: core/db.py falls back to the local SQLite file
    (data/app.db) if this isn't set, so a developer running the app
    without Neon configured yet still has a fully working app — no error,
    no warning spam, just a different (equally real) backend."""
    load_environment()
    return os.environ.get("DATABASE_URL") or None
