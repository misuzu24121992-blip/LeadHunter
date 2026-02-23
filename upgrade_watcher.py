from __future__ import annotations

"""
Verichains LeadHunter — Upgrade Watcher (Phase 1)
Monitors watchlist projects for meaningful updates:
  1. GitHub — New releases, PRs (keyword + file path filter)
  2. Snapshot — Governance proposals about upgrades

Reads watchlist from Vercel Turso DB.
Auto-creates Group B leads when upgrades detected.

Usage:
    python upgrade_watcher.py           # Run all checks
    python upgrade_watcher.py github    # GitHub only
    python upgrade_watcher.py snapshot  # Snapshot only
"""

import sys
import json
import os
import time
from datetime import datetime, timedelta, timezone

import requests


# ================================================================
#  Config (self-contained — no external config dependency)
# ================================================================

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_API_BASE = "https://api.github.com"
SNAPSHOT_GRAPHQL_URL = "https://hub.snapshot.org/graphql"

# Directories that indicate smart contract / core code changes
WATCH_DIRS = {
    "contracts", "src", "circuits", "pallets", "crates",
    "programs", "sources", "modules", "lib",
}

# Directories to ignore
IGNORE_DIRS = {
    "docs", "test", "tests", "ci", ".github", "scripts",
    "deploy", "deployments", "frontend", "app", "web",
}

# Keywords that indicate upgrade / audit-relevant changes
UPGRADE_KEYWORDS = [
    "v2", "v3", "v4", "upgrade", "migration", "audit-prep",
    "breaking", "security", "mainnet", "launch", "rewrite",
    "new version", "major", "refactor",
]

# Smart contract file extensions
CONTRACT_EXTENSIONS = (".sol", ".rs", ".move", ".go", ".cairo", ".vy")

# Snapshot governance keywords
GOVERNANCE_KEYWORDS = [
    "upgrade", "v2", "v3", "migration", "audit",
    "security", "new version", "rewrite", "major update",
]


# ================================================================
#  State Tracking (avoid duplicate alerts)
# ================================================================

STATE_FILE = os.path.join(os.path.dirname(__file__), ".watcher_state.json")


def load_state() -> dict:
    """Load previously seen items to avoid duplicate alerts."""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {"github_releases": {}, "github_prs": {}, "snapshot_proposals": {}}


def save_state(state: dict):
    """Save state to disk."""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


# ================================================================
#  GitHub Monitoring
# ================================================================

def github_headers() -> dict:
    """Get GitHub API headers with optional auth."""
    headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    return headers


def parse_github_repo(repo_url: str) -> str | None:
    """Extract owner/repo from GitHub URL or return as-is if already formatted."""
    if not repo_url:
        return None
    repo_url = repo_url.rstrip("/")
    if "github.com" in repo_url:
        parts = repo_url.replace("https://github.com/", "").replace("http://github.com/", "")
        parts = parts.split("/")
        if len(parts) >= 2:
            return f"{parts[0]}/{parts[1]}"
    elif "/" in repo_url:
        return repo_url
    return None


def check_github_releases(repo: str, state: dict) -> list[dict]:
    """Check for new releases/tags in a GitHub repo."""
    try:
        resp = requests.get(
            f"{GITHUB_API_BASE}/repos/{repo}/releases",
            headers=github_headers(),
            params={"per_page": 5},
            timeout=15,
        )
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        releases = resp.json()
    except Exception as e:
        print(f"  [GitHub] ❌ Failed to fetch releases for {repo}: {e}")
        return []

    seen_key = f"releases_{repo}"
    seen_ids = state.get("github_releases", {}).get(seen_key, [])
    new_releases = []

    for rel in releases:
        rel_id = str(rel.get("id", ""))
        if rel_id in seen_ids:
            continue

        tag = rel.get("tag_name", "")
        name = rel.get("name", tag)
        body = rel.get("body", "")[:500]
        published = rel.get("published_at", "")

        new_releases.append({
            "type": "release",
            "repo": repo,
            "tag": tag,
            "name": name,
            "body": body,
            "published": published,
            "url": rel.get("html_url", ""),
        })
        seen_ids.append(rel_id)

    state.setdefault("github_releases", {})[seen_key] = seen_ids[-20:]
    return new_releases


def check_github_prs(repo: str, state: dict) -> list[dict]:
    """Check for recently merged PRs that touch core directories."""
    try:
        resp = requests.get(
            f"{GITHUB_API_BASE}/repos/{repo}/pulls",
            headers=github_headers(),
            params={"state": "closed", "sort": "updated", "direction": "desc", "per_page": 10},
            timeout=15,
        )
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        prs = resp.json()
    except Exception as e:
        print(f"  [GitHub] ❌ Failed to fetch PRs for {repo}: {e}")
        return []

    seen_key = f"prs_{repo}"
    seen_ids = state.get("github_prs", {}).get(seen_key, [])
    cutoff = datetime.now(timezone.utc) - timedelta(days=14)
    new_prs = []

    for pr in prs:
        pr_id = str(pr.get("number", ""))
        if pr_id in seen_ids:
            continue

        # Only merged PRs
        if not pr.get("merged_at"):
            continue

        merged_at = datetime.fromisoformat(pr["merged_at"].replace("Z", "+00:00"))
        if merged_at < cutoff:
            continue

        title = pr.get("title", "")
        body = pr.get("body", "")[:300] if pr.get("body") else ""
        labels = [l.get("name", "") for l in pr.get("labels", [])]

        # Check if title/labels contain upgrade keywords
        combined_text = f"{title} {' '.join(labels)}".lower()
        has_keyword = any(kw in combined_text for kw in UPGRADE_KEYWORDS)

        # Check which files were changed
        touches_core = False
        files_changed = 0
        additions = 0
        deletions = 0
        core_files = []

        if has_keyword:
            try:
                files_resp = requests.get(
                    f"{GITHUB_API_BASE}/repos/{repo}/pulls/{pr_id}/files",
                    headers=github_headers(),
                    params={"per_page": 50},
                    timeout=15,
                )
                if files_resp.status_code == 200:
                    files = files_resp.json()
                    files_changed = len(files)
                    for f in files:
                        fname = f.get("filename", "")
                        additions += f.get("additions", 0)
                        deletions += f.get("deletions", 0)
                        first_dir = fname.split("/")[0] if "/" in fname else ""
                        if first_dir in WATCH_DIRS:
                            touches_core = True
                            core_files.append(fname)
                        if fname.endswith(CONTRACT_EXTENSIONS):
                            touches_core = True
                            core_files.append(fname)
            except Exception:
                touches_core = True

        if not has_keyword and not touches_core:
            seen_ids.append(pr_id)
            continue

        new_prs.append({
            "type": "pr",
            "repo": repo,
            "number": pr_id,
            "title": title,
            "body": body,
            "labels": labels,
            "merged_at": pr["merged_at"],
            "files_changed": files_changed,
            "additions": additions,
            "deletions": deletions,
            "touches_core": touches_core,
            "has_keyword": has_keyword,
            "core_files": core_files[:5],
            "url": pr.get("html_url", ""),
        })
        seen_ids.append(pr_id)

    state.setdefault("github_prs", {})[seen_key] = seen_ids[-50:]
    return new_prs


def run_github_monitor(watchlist: list[dict], state: dict) -> list[dict]:
    """Run GitHub monitoring for all watchlist projects."""
    print("\n" + "=" * 60)
    print("🐙 GitHub — Upgrade Detection")
    print("=" * 60)

    all_changes = []

    for project in watchlist:
        repo_url = project.get("github_repo", "")
        repo = parse_github_repo(repo_url)
        if not repo:
            continue

        name = project.get("name", repo)
        print(f"\n  📦 Checking {name} ({repo})...")

        # Check releases
        releases = check_github_releases(repo, state)
        for r in releases:
            r["project_name"] = name
            r["project_data"] = project
        all_changes.extend(releases)

        # Check PRs
        prs = check_github_prs(repo, state)
        for p in prs:
            p["project_name"] = name
            p["project_data"] = project
        all_changes.extend(prs)

        if releases:
            print(f"    🏷️  {len(releases)} new release(s)")
        if prs:
            print(f"    🔀 {len(prs)} meaningful PR(s)")
        if not releases and not prs:
            print(f"    ✅ No updates")

        time.sleep(0.5)  # Rate limiting

    print(f"\n  Total changes detected: {len(all_changes)}")
    return all_changes


# ================================================================
#  Snapshot Governance Monitoring
# ================================================================

def check_snapshot_proposals(spaces: list[dict], state: dict) -> list[dict]:
    """Check Snapshot.org for governance proposals mentioning upgrades."""
    print("\n" + "=" * 60)
    print("🗳️ Snapshot — Governance Proposals")
    print("=" * 60)

    # Build list of space IDs from watchlist
    space_ids = []
    space_map = {}
    for project in spaces:
        space_id = project.get("snapshot_space", "")
        if space_id:
            space_ids.append(space_id)
            space_map[space_id] = project

    if not space_ids:
        print("  ⚠️  No Snapshot spaces configured in watchlist.")
        print("  💡 Add snapshot_space to watchlist items for governance monitoring.")
        return []

    query = """
    query Proposals($spaces: [String!]) {
        proposals(
            first: 50,
            skip: 0,
            where: { space_in: $spaces, state: "active" },
            orderBy: "created",
            orderDirection: desc
        ) {
            id
            title
            body
            state
            space { id name }
            created
            end
            author
            link
        }
    }
    """

    try:
        resp = requests.post(
            SNAPSHOT_GRAPHQL_URL,
            json={"query": query, "variables": {"spaces": space_ids}},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        proposals = data.get("data", {}).get("proposals", [])
    except Exception as e:
        print(f"  [Snapshot] ❌ API failed: {e}")
        return []

    seen_ids = state.get("snapshot_proposals", {})
    new_proposals = []

    for prop in proposals:
        prop_id = prop.get("id", "")
        if prop_id in seen_ids:
            continue

        title = prop.get("title", "").lower()
        body = (prop.get("body", "") or "")[:500].lower()
        combined = f"{title} {body}"

        has_keyword = any(kw in combined for kw in GOVERNANCE_KEYWORDS)
        if not has_keyword:
            seen_ids[prop_id] = True
            continue

        space_id = prop.get("space", {}).get("id", "")
        space_name = prop.get("space", {}).get("name", space_id)
        project = space_map.get(space_id, {})

        end_ts = prop.get("end", 0)
        end_date = datetime.fromtimestamp(end_ts, timezone.utc).strftime("%Y-%m-%d %H:%M UTC") if end_ts else "Unknown"

        new_proposals.append({
            "type": "governance",
            "space": space_name,
            "space_id": space_id,
            "title": prop.get("title", ""),
            "body": prop.get("body", "")[:300],
            "state": prop.get("state", ""),
            "end_date": end_date,
            "link": prop.get("link", ""),
            "project_name": project.get("name", space_name),
            "project_data": project,
        })

        seen_ids[prop_id] = True
        print(f"  🗳️ [{space_name}] {prop.get('title', '')[:60]}")

    state["snapshot_proposals"] = seen_ids
    if not new_proposals:
        print("  ✅ No new upgrade proposals")

    return new_proposals


# ================================================================
#  Keyword-based Filter (replaces AI noise filter — $0 cost)
# ================================================================

def filter_changes(changes: list[dict]) -> list[dict]:
    """Filter changes using keyword + file path rules. No AI needed."""
    if not changes:
        return []

    print(f"\n[Filter] 🔍 Filtering {len(changes)} changes...")

    meaningful = []
    for change in changes:
        keep = False
        reason = ""

        if change["type"] == "release":
            # Releases are always meaningful
            keep = True
            reason = f"New release: {change.get('tag', '')}"

        elif change["type"] == "pr":
            # PR must have keyword AND touch core files
            if change.get("has_keyword") and change.get("touches_core"):
                keep = True
                reason = f"PR touches core + keyword: {change.get('title', '')[:40]}"
            elif change.get("has_keyword"):
                # Keyword but unsure about files — keep with lower confidence
                keep = True
                reason = f"PR has upgrade keyword: {change.get('title', '')[:40]}"

        elif change["type"] == "governance":
            # Governance proposals already keyword-filtered
            keep = True
            reason = f"Governance: {change.get('title', '')[:40]}"

        if keep:
            change["filter_reason"] = reason
            meaningful.append(change)
            print(f"  ✅ KEEP: [{change['type']}] {change.get('project_name', '')} — {reason[:60]}")
        else:
            print(f"  ⬇️  SKIP: [{change['type']}] {change.get('project_name', '')} — no match")

    print(f"\n  Kept {len(meaningful)} / {len(changes)} changes")
    return meaningful


# ================================================================
#  Auto-create Group B Leads
# ================================================================

def create_group_b_leads(changes: list[dict], db_module=None) -> int:
    """Create Group B leads from meaningful upgrade changes."""
    if not changes or not db_module:
        return 0

    created = 0
    existing_names = set()
    try:
        existing_names = set(db_module.get_lead_names())
    except Exception:
        pass

    for change in changes:
        project_name = change.get("project_name", "Unknown")
        project_data = change.get("project_data", {})

        # Build lead name with context
        if change["type"] == "release":
            lead_name = f"{project_name} — {change.get('tag', 'new release')}"
        elif change["type"] == "pr":
            lead_name = f"{project_name} — PR: {change.get('title', '')[:40]}"
        elif change["type"] == "governance":
            lead_name = f"{project_name} — Proposal: {change.get('title', '')[:40]}"
        else:
            lead_name = f"{project_name} — Upgrade detected"

        # Skip if lead with same Project name already exists
        if project_name in existing_names:
            print(f"  ⏭️  {project_name} already in pipeline, skipping lead creation")
            continue

        # Build summary
        if change["type"] == "release":
            summary = (
                f"🏷️ New release {change.get('tag', '')} detected in {change.get('repo', '')}. "
                f"{change.get('body', '')[:200]}"
            )
        elif change["type"] == "pr":
            summary = (
                f"🔀 Merged PR: {change.get('title', '')}. "
                f"Files changed: {change.get('files_changed', '?')}, "
                f"+{change.get('additions', 0)} / -{change.get('deletions', 0)}. "
                f"{'Touches core contracts.' if change.get('touches_core') else ''} "
                f"Link: {change.get('url', '')}"
            )
        elif change["type"] == "governance":
            summary = (
                f"🗳️ Governance proposal: {change.get('title', '')}. "
                f"Voting ends: {change.get('end_date', '?')}. "
                f"{change.get('body', '')[:150]}"
            )
        else:
            summary = f"Upgrade detected for {project_name}"

        lead = {
            "name": project_name,
            "category": project_data.get("category", "DeFi"),
            "score": 65,  # Default Group B score — will be refined by AI scoring
            "priority": "WARM",
            "source": "Upgrade Watcher",
            "signals": [change.get("filter_reason", "Upgrade detected")],
            "summary": summary,
            "funding": project_data.get("notes", ""),
            "tech": "",
            "audit_status": project_data.get("auditor", "") or "Unknown — needs review",
            "pitch_services": ["Smart Contract Re-audit", "Upgrade Review"],
            "score_breakdown": {
                "Audit Need": "18/25 — Upgrade detected, re-audit likely needed",
                "Funding & Budget": "10/15 — Active project",
                "Category Fit": "12/15 — Existing protocol",
                "Growth & Timing": "9/10 — Upgrade in progress",
                "Verichains Moat": "3/5 — Standard",
                "Base Score": "13/30 — Group B baseline",
            },
            "scored_by": "upgrade_watcher",
            "lead_group": "B",
            "github_url": project_data.get("github_repo", ""),
            "twitter_url": project_data.get("x_account", ""),
        }

        try:
            lead_id = db_module.insert_lead(lead)
            if lead_id:
                created += 1
                existing_names.add(project_name)
                print(f"  🆕 Created Group B lead: {project_name} (ID: {lead_id})")
            else:
                print(f"  ⏭️  {project_name} — duplicate, skipped")
        except Exception as e:
            print(f"  ❌ Failed to create lead for {project_name}: {e}")

    return created


# ================================================================
#  Main
# ================================================================

def run_scan(watchlist: list[dict], db_module=None) -> dict:
    """
    Run full upgrade scan. Called from server.py or standalone.
    Returns summary dict.
    """
    print("🔍 Verichains LeadHunter — Upgrade Watcher")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📦 Projects to monitor: {len(watchlist)}")
    print()

    sources = sys.argv[1:] if len(sys.argv) > 1 else ["github", "snapshot"]

    state = load_state()
    all_changes = []

    if "github" in sources:
        github_changes = run_github_monitor(watchlist, state)
        all_changes.extend(github_changes)

    if "snapshot" in sources:
        snapshot_changes = check_snapshot_proposals(watchlist, state)
        all_changes.extend(snapshot_changes)

    # Filter through keyword rules
    meaningful = filter_changes(all_changes)

    # Auto-create Group B leads
    leads_created = 0
    if meaningful and db_module:
        leads_created = create_group_b_leads(meaningful, db_module)

    # Save state
    save_state(state)

    # Summary
    print("\n" + "=" * 60)
    print("📊 UPGRADE WATCHER SUMMARY")
    print("=" * 60)
    print(f"  📦 Projects monitored: {len(watchlist)}")
    print(f"  🔔 Raw changes detected: {len(all_changes)}")
    print(f"  ✅ Meaningful (after filter): {len(meaningful)}")
    print(f"  🆕 Group B leads created: {leads_created}")
    print()

    return {
        "projects_monitored": len(watchlist),
        "raw_changes": len(all_changes),
        "meaningful": len(meaningful),
        "leads_created": leads_created,
        "changes": [
            {
                "project": c.get("project_name", "?"),
                "type": c["type"],
                "title": c.get("title", c.get("name", c.get("tag", ""))),
                "url": c.get("url", c.get("link", "")),
                "reason": c.get("filter_reason", ""),
            }
            for c in meaningful
        ],
    }


def main():
    """Standalone CLI entry point."""
    # Try to load from local watchlist or DB
    try:
        import database as db
        db.init_tables(db.get_conn())
        watchlist_rows = db.get_watchlist()
        watchlist = [dict(r) if hasattr(r, 'keys') else r for r in watchlist_rows]
        if not watchlist:
            raise ValueError("Empty watchlist")
        print(f"[Watchlist] ✅ Loaded {len(watchlist)} projects from database")
        result = run_scan(watchlist, db_module=db)
    except Exception as e:
        print(f"[Watchlist] ⚠️ DB not available ({e}), trying local file...")
        watchlist_file = os.path.join(os.path.dirname(__file__), "watchlist.json")
        if os.path.exists(watchlist_file):
            with open(watchlist_file, "r") as f:
                watchlist = json.load(f)
            print(f"[Watchlist] 📂 Loaded {len(watchlist)} projects from watchlist.json")
            result = run_scan(watchlist, db_module=None)
        else:
            print("❌ No watchlist found. Add projects via the UI or create watchlist.json")
            return

    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
