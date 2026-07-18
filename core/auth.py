"""Authentication + the account-type axis (Praxis Point staff vs client users).

TWO AXES:
  * account_type — the TENANT BOUNDARY. 'praxis_staff' sees ALL clients and can switch
    between them; 'client_user' is pinned to ONE home tenant, read-only, switcher hidden.
    This is the axis that makes the app a real multi-tenant SaaS rather than an open
    internal tool.
  * role_key — the persona (IR/CEO/CFO/CRO/Legal), controlling which pages a user sees
    within a tenant. Pre-existing (config.client_config.ROLE_PERMISSIONS); unchanged.

SECURITY MODEL — the two guarantees:
  1. TENANT ISOLATION. The set of tenants a session may touch is derived from the
     AUTHENTICATED user server-side (allowed_clients), never from the client-supplied
     active_client_id cookie. A client_user cannot cross tenants even by forging the cookie
     (see app_nicegui._bind_active_client's clamp).
  2. READ-ONLY. A client_user session is marked read-only in core.db, so writes are refused
     at the DATA layer regardless of whether a given UI control happens to be gated. Belt and
     suspenders — the UI hides mutating controls; the data layer guarantees they can't write.

Password hashing is stdlib PBKDF2-HMAC-SHA256 (no new dependency), stored as
"pbkdf2$<iterations>$<salt_hex>$<hash_hex>".
"""

import hashlib
import hmac
import os
import secrets
from datetime import datetime

from core import db

_ITERATIONS = 240_000
STAFF = "praxis_staff"
CLIENT = "client_user"


# ── password hashing (stdlib) ──────────────────────────────────────────────
def hash_password(pw):
    salt = secrets.token_bytes(16)
    h = hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), salt, _ITERATIONS)
    return f"pbkdf2${_ITERATIONS}${salt.hex()}${h.hex()}"


def verify_password(pw, stored):
    try:
        scheme, iters, salt_hex, hash_hex = stored.split("$")
        if scheme != "pbkdf2":
            return False
        h = hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), bytes.fromhex(salt_hex), int(iters))
        return hmac.compare_digest(h.hex(), hash_hex)  # constant-time
    except Exception:
        return False


# ── users table access ─────────────────────────────────────────────────────
_COLS = ("user_id", "display_name", "password_hash", "account_type",
         "home_client_id", "role_key", "active", "must_change_password",
         "created_at", "last_login")


def _row(r):
    d = dict(zip(_COLS, r))
    d["active"] = bool(d["active"])
    d["must_change_password"] = bool(d["must_change_password"])
    return d


def get_user(user_id):
    if not user_id:
        return None
    conn = db.get_connection()
    pg = db.connection_is_postgres(conn)
    try:
        cur = conn.cursor()
        ph = "%s" if pg else "?"
        cur.execute(f"SELECT {', '.join(_COLS)} FROM users WHERE lower(user_id) = lower({ph})",
                    (user_id,))
        row = cur.fetchone()
        return _row(row) if row else None
    finally:
        conn.close()


def _count(where="", params=()):
    conn = db.get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) FROM users {where}", params)
        return cur.fetchone()[0]
    finally:
        conn.close()


def create_user(user_id, password, account_type, home_client_id=None, role_key="IR",
                display_name=None, must_change=True):
    """Insert a user. No-op (returns False) if the user_id already exists — so seeding is
    idempotent. Returns True if created."""
    if get_user(user_id):
        return False
    conn = db.get_connection()
    pg = db.connection_is_postgres(conn)
    try:
        cur = conn.cursor()
        ph = "%s" if pg else "?"
        now = datetime.now()
        cur.execute(
            f"INSERT INTO users (user_id, display_name, password_hash, account_type, "
            f"home_client_id, role_key, active, must_change_password, created_at) "
            f"VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})",
            (user_id, display_name or user_id, hash_password(password), account_type,
             home_client_id, role_key, True, bool(must_change),
             now if pg else now.isoformat()))
        conn.commit()
        return True
    finally:
        conn.close()


def set_password(user_id, new_password):
    """Set a new password and clear must_change_password (used by the forced-change flow)."""
    conn = db.get_connection()
    pg = db.connection_is_postgres(conn)
    try:
        cur = conn.cursor()
        ph = "%s" if pg else "?"
        cur.execute(
            f"UPDATE users SET password_hash = {ph}, must_change_password = {ph} "
            f"WHERE lower(user_id) = lower({ph})",
            (hash_password(new_password), False, user_id))
        conn.commit()
    finally:
        conn.close()


def list_users():
    """All users, ordered staff-first then by tenant/email — for the staff admin screen."""
    conn = db.get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            f"SELECT {', '.join(_COLS)} FROM users "
            f"ORDER BY account_type, COALESCE(home_client_id, ''), user_id")
        return [_row(r) for r in cur.fetchall()]
    finally:
        conn.close()


def admin_reset_password(user_id, new_password=None):
    """Reset a user's password (to new_password, or the shared default) AND re-arm
    must_change_password so they're forced to rotate on next login. Returns the password
    that was set, so staff can convey it to the user."""
    pw = new_password or default_user_password()
    conn = db.get_connection()
    pg = db.connection_is_postgres(conn)
    try:
        cur = conn.cursor()
        ph = "%s" if pg else "?"
        cur.execute(
            f"UPDATE users SET password_hash = {ph}, must_change_password = {ph} "
            f"WHERE lower(user_id) = lower({ph})",
            (hash_password(pw), True, user_id))
        conn.commit()
    finally:
        conn.close()
    return pw


def set_user_active(user_id, active):
    """Enable/disable a login without deleting it. authenticate() rejects inactive users."""
    conn = db.get_connection()
    pg = db.connection_is_postgres(conn)
    try:
        cur = conn.cursor()
        ph = "%s" if pg else "?"
        cur.execute(f"UPDATE users SET active = {ph} WHERE lower(user_id) = lower({ph})",
                    (bool(active), user_id))
        conn.commit()
    finally:
        conn.close()


def touch_login(user_id):
    conn = db.get_connection()
    pg = db.connection_is_postgres(conn)
    try:
        cur = conn.cursor()
        ph = "%s" if pg else "?"
        now = datetime.now()
        cur.execute(f"UPDATE users SET last_login = {ph} WHERE lower(user_id) = lower({ph})",
                    (now if pg else now.isoformat(), user_id))
        conn.commit()
    finally:
        conn.close()


def authenticate(user_id, password):
    """Return the user dict on success, else None. Does a dummy verify on unknown users to
    keep timing uniform (no user-enumeration side channel)."""
    user = get_user(user_id)
    if not user or not user["active"]:
        verify_password(password, "pbkdf2$1$00$00")  # constant-ish work
        return None
    return user if verify_password(password, user["password_hash"]) else None


# ── the account-type axis ──────────────────────────────────────────────────
def allowed_clients(user):
    """Tenants this user may touch — derived from identity, NOT from any cookie. Staff: all
    registered clients. client_user: only its home tenant. This is the isolation boundary."""
    from config.client_config import CLIENT_REGISTRY
    if not user:
        return []
    if user["account_type"] == STAFF:
        return list(CLIENT_REGISTRY.keys())
    hc = user.get("home_client_id")
    return [hc] if hc in CLIENT_REGISTRY else []


def is_staff(user):
    return bool(user) and user["account_type"] == STAFF


def is_client_user(user):
    return bool(user) and user["account_type"] == CLIENT


# ── seeding ────────────────────────────────────────────────────────────────
# The two standard client logins every tenant gets, regardless of whether its roster is
# filled in — a generic IR pair so onboarding always hands the client the same two sign-ins.
# (handle, display_name); the login id is "<handle>@<ticker>".
STANDARD_CLIENT_LOGINS = [
    ("directorofir", "Director of IR"),
    ("irassistant",  "IRassistant"),
]


def default_user_password():
    return os.environ.get("DEFAULT_USER_PASSWORD", "IRconnect1")


def seed_admin_from_env():
    """First-boot bootstrap: if NO praxis_staff exists yet, create one from ADMIN_EMAIL /
    ADMIN_PASSWORD. must_change_password is set — the env password is a one-time bootstrap
    and should be rotated at first login. No-op if any staff user already exists or the env
    vars are absent."""
    email = os.environ.get("ADMIN_EMAIL")
    pw = os.environ.get("ADMIN_PASSWORD")
    if not email or not pw:
        return None
    if _count("WHERE account_type = " + ("%s" if db.postgres_configured() else "?"), (STAFF,)) > 0:
        return None
    if create_user(email, pw, STAFF, None, "IR", display_name="Praxis Point Admin", must_change=True):
        print(f"[auth] seeded first Praxis Point admin: {email} (must change password on first login)")
        return email
    return None


def seed_client_users(client_id):
    """Seed the two STANDARD client_user logins (Director of IR, IRassistant) for a tenant —
    both read-only, tenant-scoped, role IR, seeded with the shared default password and forced
    to change it on first sign-in. The same pair for every client, independent of its roster, so
    onboarding is uniform. Idempotent. Returns the list of user_ids created."""
    from config.client_config import get_client, CLIENT_REGISTRY
    if client_id not in CLIENT_REGISTRY:
        return []
    client = get_client(client_id)
    ticker = (client.get("ticker") or client_id).lower()
    pw = default_user_password()
    created = []
    for handle, display in STANDARD_CLIENT_LOGINS:
        uid = f"{handle}@{ticker}"
        if create_user(uid, pw, CLIENT, client_id, "IR", display_name=display, must_change=True):
            created.append(uid)
    return created


def seed_all_client_users():
    """Seed client_user accounts for every registered tenant. Idempotent — safe on every boot."""
    from config.client_config import CLIENT_REGISTRY
    out = {}
    for cid in CLIENT_REGISTRY:
        made = seed_client_users(cid)
        if made:
            out[cid] = made
    return out
