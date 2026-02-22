from __future__ import annotations

"""
Verichains LeadHunter — Upgrade Watcher Script
Monitors target projects for meaningful updates:
  1. GitHub — New releases, PRs, branches (with AI noise filter)
  2. Snapshot — Governance proposals about upgrades

Reads target project list from Airtable Watchlist or local JSON fallback.

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

import config
import ai_scorer
import airtable_client
import telegram_bot


# ================================================================
#  Local Watchlist Fallback
# ================================================================

WATCHLIST_FILE = os.path.join(os.path.dirname(__file__), "watchlist.json")


def load_watchlist() -> list[dict]:
    """Load target projects from Airtable or local JSON fallback."""
    # Try Airtable first
    projects = airtable_client.get_watchlist()
    if projects:
        print(f"[Watchlist] ✅ Loaded {len(projects)} projects from Airtable")
        return projects

    # Fallback to local JSON
    if os.path.exists(WATCHLIST_FILE):
        with open(WATCHLIST_FILE, "r") as f:
            projects = json.load(f)
        print(f"[Watchlist] 📂 Loaded {len(projects)} projects from local watchlist.json")
        return projects

    print("[Watchlist] ⚠️  No watchlist found. Create watchlist.json or setup Airtable.")
    print("[Watchlist] 💡 See watchlist.example.json for format.")
    return []


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
    if config.GITHUB_TOKEN:
        headers["Authorization"] = f"token {config.GITHUB_TOKEN}"
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
            f"{config.GITHUB_API_BASE}/repos/{repo}/releases",
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

        # Update seen state
        seen_ids.append(rel_id)

    state.setdefault("github_releases", {})[seen_key] = seen_ids[-20:]
    return new_releases


def check_github_prs(repo: str, state: dict) -> list[dict]:
    """Check for recently merged PRs that touch core directories."""
    try:
        resp = requests.get(
            f"{config.GITHUB_API_BASE}/repos/{repo}/pulls",
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
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
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
        has_keyword = any(kw in combined_text for kw in config.GITHUB_UPGRADE_KEYWORDS)

        # Check which files were changed (if keyword match or we want to be thorough)
        touches_core = False
        files_changed = 0
        additions = 0
        deletions = 0

        if has_keyword:
            try:
                files_resp = requests.get(
                    f"{config.GITHUB_API_BASE}/repos/{repo}/pulls/{pr_id}/files",
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
                        # Check if file is in a core directory
                        first_dir = fname.split("/")[0] if "/" in fname else ""
                        if first_dir in config.GITHUB_WATCH_DIRS:
                            touches_core = True
                        # Also check file extension
                        if fname.endswith((".sol", ".rs", ".move", ".go", ".cairo")):
                            touches_core = True
            except Exception:
                touches_core = True  # Assume meaningful if we can't check

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
    space_map = {}  # Map space_id -> project info
    for project in spaces:
        space_id = project.get("snapshot_space", "")
        if space_id:
            space_ids.append(space_id)
            space_map[space_id] = project

    if not space_ids:
        print("  ⚠️  No Snapshot spaces configured in watchlist.")
        return []

    # GraphQL query for recent proposals
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
            config.SNAPSHOT_GRAPHQL_URL,
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

        # Check for upgrade keywords
        has_keyword = any(kw in combined for kw in config.SNAPSHOT_UPGRADE_KEYWORDS)
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
#  AI Filtering & Alert Pipeline
# ================================================================

def process_changes(changes: list[dict]) -> list[dict]:
    """Filter changes through AI noise filter and send alerts for meaningful ones."""
    if not changes:
        return []

    print(f"\n[Pipeline] 🧠 Filtering {len(changes)} changes through AI...")

    meaningful = []
    for change in changes:
        # Format change for noise filter
        if change["type"] == "release":
            desc = (
                f"GitHub Release in repo {change['repo']}:\n"
                f"Tag: {change['tag']}\n"
                f"Name: {change['name']}\n"
                f"Release notes: {change['body']}"
            )
        elif change["type"] == "pr":
            desc = (
                f"GitHub PR merged in repo {change['repo']}:\n"
                f"Title: {change['title']}\n"
                f"Labels: {', '.join(change.get('labels', []))}\n"
                f"Files changed: {change.get('files_changed', '?')}, "
                f"+{change.get('additions', '?')} -{change.get('deletions', '?')}\n"
                f"Touches core dirs: {change.get('touches_core', '?')}\n"
                f"Body: {change.get('body', '')[:200]}"
            )
        elif change["type"] == "governance":
            # Governance proposals skip noise filter — already keyword-filtered
            meaningful.append(change)
            project = change.get("project_data", {})
            telegram_bot.alert_governance({
                "space": change["project_name"],
                "title": change["title"],
                "state": change["state"],
                "end_date": change["end_date"],
                "summary": change["body"][:200],
            })
            continue
        else:
            continue

        # AI noise filter
        result = ai_scorer.filter_noise(desc)
        if result and result.get("is_meaningful", False) and result.get("confidence", 0) >= 0.6:
            meaningful.append(change)
            project = change.get("project_data", {})

            # Send Telegram alert
            telegram_bot.alert_upgrade({
                "name": change.get("project_name", change.get("repo", "Unknown")),
                "is_existing_client": project.get("client_type") == "Khách cũ",
                "change_type": "Release" if change["type"] == "release" else "PR Merged",
                "change_detail": change.get("name", change.get("title", "")),
                "lines_changed": f"+{change.get('additions', '?')} / -{change.get('deletions', '?')}" if change["type"] == "pr" else "N/A",
                "last_audit": project.get("last_audit_date", "Unknown"),
                "summary": result.get("reason", ""),
                "score": 85 if project.get("client_type") == "Khách cũ" else 70,
            })

            print(f"  ✅ MEANINGFUL: [{change['type']}] {change.get('project_name', '')} — {result.get('reason', '')[:60]}")
        else:
            reason = result.get("reason", "filtered") if result else "AI unavailable"
            print(f"  ⬇️ NOISE: [{change['type']}] {change.get('project_name', '')} — {reason[:60]}")

        time.sleep(0.3)

    return meaningful


# ================================================================
#  Main
# ================================================================

def main():
    print("🔍 Verichains LeadHunter — Upgrade Watcher")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    sources = sys.argv[1:] if len(sys.argv) > 1 else ["github", "snapshot"]

    # Load watchlist
    watchlist = load_watchlist()
    if not watchlist:
        print("❌ No projects to watch. Exiting.")
        print("💡 Create watchlist.json or setup Airtable Watchlist.")
        return

    # Load state
    state = load_state()

    all_changes = []

    if "github" in sources:
        github_changes = run_github_monitor(watchlist, state)
        all_changes.extend(github_changes)

    if "snapshot" in sources:
        snapshot_changes = check_snapshot_proposals(watchlist, state)
        all_changes.extend(snapshot_changes)

    # Process through AI filter
    meaningful = process_changes(all_changes)

    # Save state
    save_state(state)

    # Summary
    print("\n" + "=" * 60)
    print("📊 UPGRADE WATCHER SUMMARY")
    print("=" * 60)
    print(f"  📦 Projects monitored: {len(watchlist)}")
    print(f"  🔔 Raw changes detected: {len(all_changes)}")
    print(f"  ✅ Meaningful (after AI filter): {len(meaningful)}")
    print()

    if meaningful:
        digest = (
            f"🔍 <b>Upgrade Watcher Report</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 Monitored: {len(watchlist)} | 🔔 Changes: {len(all_changes)} | ✅ Meaningful: {len(meaningful)}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
        )
        for m in meaningful:
            digest += f"• <b>{m.get('project_name', '?')}</b> [{m['type']}] — {m.get('title', m.get('name', ''))[:50]}\n"
        telegram_bot.send_message(digest)

    print("✅ Upgrade watch complete!")


if __name__ == "__main__":
    main()
