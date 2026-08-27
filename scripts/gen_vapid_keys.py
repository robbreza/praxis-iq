#!/usr/bin/env python
"""Generate a stable VAPID keypair for IRconnect Web Push (phone alerts).

Run this LOCALLY, then paste the printed values into your host's env
(Render -> service -> Environment, marked secret). Setting these env vars decouples the push
identity from the database: the app otherwise auto-generates and persists a keypair in Neon
(lighthouse_vapid.json), which works fine, but a DB reset/migration would lose it and
invalidate every phone subscription already out there. Env-provided keys survive DB changes.

Format is guaranteed correct because this reuses the app's own generator (lighthouse.push):
  VAPID_PUBLIC_KEY  = base64url of the X9.62 uncompressed EC point (the browser applicationServerKey)
  VAPID_PRIVATE_KEY = PKCS8 PEM (what pywebpush's Vapid01.from_pem expects)
  VAPID_SUBJECT     = a mailto: or https: contact push services can reach

SECURITY: VAPID_PRIVATE_KEY is a secret. This script only prints to stdout; it writes and
persists nothing. Do not commit the output. Do not paste it into a shared channel.

Usage:
    python scripts/gen_vapid_keys.py --subject mailto:ir@praxispointir.com
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    ap = argparse.ArgumentParser(description="Generate a VAPID keypair for IRconnect phone alerts.")
    ap.add_argument("--subject", default="mailto:ir@praxispointir.com",
                    help="VAPID contact shown to push services (mailto:you@domain or https://your-site)")
    args = ap.parse_args()

    from lighthouse.push import _generate_keys      # reuse the app's exact key format
    k = _generate_keys()

    print("# ===== VAPID keys — paste into Render -> Environment (mark secret). DO NOT COMMIT. =====")
    print(f"VAPID_SUBJECT={args.subject}")
    print(f"VAPID_PUBLIC_KEY={k['public']}")
    print("# VAPID_PRIVATE_KEY: set as ONE env var, INCLUDING the BEGIN/END lines and newlines below.")
    print("# (Render's dashboard accepts multi-line values — paste the whole block as the value.)")
    print("VAPID_PRIVATE_KEY<<<")
    print(k["private_pem"].strip())
    print(">>>")
    print()
    print("# Verify after deploy:  curl https://<your-app>/push/vapid-public-key   -> prints VAPID_PUBLIC_KEY")
    print("# NOTE: changing this keypair later invalidates every existing phone subscription")
    print("#       (users must re-tap 'Enable phone alerts'). Generate once, keep it stable.")


if __name__ == "__main__":
    main()
