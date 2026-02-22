from __future__ import annotations

"""
Verichains LeadHunter — Airtable Client
Push leads to Airtable Pipeline Tracker & Watchlist.
Uses pyairtable for clean API interaction.
"""

import config

try:
    from pyairtable import Api
except ImportError:
    Api = None
    print("[Airtable] ⚠️  pyairtable not installed. Run: pip install pyairtable")

_api = None
_pipeline_table = None
_watchlist_table = None


def _init():
    """Lazy-initialize Airtable connection."""
    global _api, _pipeline_table, _watchlist_table
    if _api is not None:
        return True

    if not Api:
        return False

    if not config.AIRTABLE_API_KEY or not config.AIRTABLE_BASE_ID:
        print("[Airtable] ⚠️  API key or Base ID not configured. Data will only print to console.")
        return False

    try:
        _api = Api(config.AIRTABLE_API_KEY)
        _pipeline_table = _api.table(config.AIRTABLE_BASE_ID, config.AIRTABLE_PIPELINE_TABLE)
        _watchlist_table = _api.table(config.AIRTABLE_BASE_ID, config.AIRTABLE_WATCHLIST_TABLE)
        return True
    except Exception as e:
        print(f"[Airtable] ❌ Init failed: {e}")
        return False


def push_lead(lead: dict) -> bool:
    """
    Push a scored lead to the Pipeline Tracker table.

    Args:
        lead: Dict from AI scorer with keys like name, category, score, etc.
    """
    fields = {
        "Project Name": lead.get("name", "Unknown"),
        "Category": lead.get("category", "Other"),
        "Score": lead.get("score", 0),
        "Priority": lead.get("priority", "LOW"),
        "Source": lead.get("source", "Unknown"),
        "Trigger": ", ".join(lead.get("signals", [])),
        "Stage": "Discovered",
        "Funding": lead.get("funding", "N/A"),
        "AI Summary": lead.get("summary", ""),
    }

    if not _init():
        print(f"[Airtable] 📋 Would push lead: {fields['Project Name']} (Score: {fields['Score']})")
        return False

    try:
        # Check for duplicates by project name
        existing = _pipeline_table.all(formula=f"{{Project Name}} = '{fields['Project Name']}'")
        if existing:
            print(f"[Airtable] ⏭️  '{fields['Project Name']}' already exists in pipeline. Skipping.")
            return False

        _pipeline_table.create(fields)
        print(f"[Airtable] ✅ Pushed: {fields['Project Name']} (Score: {fields['Score']})")
        return True
    except Exception as e:
        print(f"[Airtable] ❌ Push failed: {e}")
        return False


def push_leads_batch(leads: list[dict]) -> int:
    """Push multiple leads. Returns count of successfully pushed."""
    count = 0
    for lead in leads:
        if push_lead(lead):
            count += 1
    return count


def get_watchlist() -> list[dict]:
    """
    Get all projects from the Watchlist (for upgrade_watcher to monitor).

    Returns:
        List of dicts with project info (name, github_repo, snapshot_space, etc.)
    """
    if not _init():
        print("[Airtable] ⚠️  Cannot read watchlist — Airtable not configured.")
        return []

    try:
        records = _watchlist_table.all()
        return [
            {
                "name": r["fields"].get("Project Name", ""),
                "github_repo": r["fields"].get("GitHub Repo", ""),
                "snapshot_space": r["fields"].get("Snapshot Space", ""),
                "x_account": r["fields"].get("X Account", ""),
                "category": r["fields"].get("Category", ""),
                "last_audit_date": r["fields"].get("Last Audit Date", ""),
                "auditor": r["fields"].get("Auditor", ""),
                "client_type": r["fields"].get("Client Type", ""),
                "notes": r["fields"].get("Notes", ""),
            }
            for r in records
        ]
    except Exception as e:
        print(f"[Airtable] ❌ Failed to read watchlist: {e}")
        return []


def get_pipeline_projects() -> list[str]:
    """Get list of project names already in pipeline (for dedup)."""
    if not _init():
        return []

    try:
        records = _pipeline_table.all(fields=["Project Name"])
        return [r["fields"].get("Project Name", "") for r in records]
    except Exception as e:
        print(f"[Airtable] ❌ Failed to read pipeline: {e}")
        return []


def get_watchlist_by_category(category: str) -> list[dict]:
    """Get watchlist projects filtered by category (for incident matching)."""
    if not _init():
        return []

    try:
        records = _watchlist_table.all(
            formula=f"{{Category}} = '{category}'"
        )
        return [
            {
                "name": r["fields"].get("Project Name", ""),
                "category": r["fields"].get("Category", ""),
                "client_type": r["fields"].get("Client Type", ""),
            }
            for r in records
        ]
    except Exception as e:
        print(f"[Airtable] ❌ Failed to filter watchlist: {e}")
        return []


# ---- Quick test ----
if __name__ == "__main__":
    test_lead = {
        "name": "TestProtocol",
        "category": "DeFi",
        "score": 75,
        "priority": "WARM",
        "source": "Test",
        "funding": "$2M Seed",
        "summary": "Test lead for Airtable integration",
        "signals": ["Test signal"],
    }
    push_lead(test_lead)
