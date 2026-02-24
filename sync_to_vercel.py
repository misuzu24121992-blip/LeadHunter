"""
Sync local leads to Vercel DB.

Usage:
    python3 sync_to_vercel.py

Reads all leads from local DB and pushes them to Vercel via /api/sync-leads.
This ensures Vercel dashboard shows the same data as local (full scan results).
"""

import json
import requests
import database as db

VERCEL_URL = "https://leadhunter-nine.vercel.app"


def sync():
    leads = db.get_leads(limit=500)
    if not leads:
        print("❌ No leads in local DB to sync.")
        return

    print(f"📤 Syncing {len(leads)} leads to Vercel...")

    # Prepare payload
    payload = {"leads": leads}

    try:
        resp = requests.post(
            f"{VERCEL_URL}/api/sync-leads",
            json=payload,
            timeout=30,
        )
        if resp.status_code == 200:
            result = resp.json()
            print(f"✅ Synced: {result.get('synced', 0)} leads pushed to Vercel")
        else:
            print(f"❌ Sync failed: HTTP {resp.status_code} — {resp.text[:200]}")
    except Exception as e:
        print(f"❌ Sync error: {e}")


if __name__ == "__main__":
    sync()
