from __future__ import annotations

"""
Verichains LeadHunter — Incident Radar Script
Monitors for security incidents (hacks, exploits, vulnerabilities):
  1. Rekt News RSS feed
  2. PeckShield / Cyvers on X (keyword-based)

When incident detected:
  - Identifies affected category
  - Pulls competitor protocols from Watchlist
  - Drafts FUD-driven outreach via AI
  - Sends Telegram alert with target list

Usage:
    python incident_radar.py
"""

import json
import os
import time
from datetime import datetime, timezone

import requests

try:
    import feedparser
except ImportError:
    feedparser = None
    print("[Incident] ⚠️  feedparser not installed. Run: pip install feedparser")

import config
import ai_scorer
import airtable_client
import telegram_bot


# ================================================================
#  State Tracking
# ================================================================

STATE_FILE = os.path.join(os.path.dirname(__file__), ".incident_state.json")


def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {"seen_rekt": [], "seen_alerts": []}


def save_state(state: dict):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


# ================================================================
#  Rekt News RSS Monitor
# ================================================================

def fetch_rekt_news(state: dict) -> list[dict]:
    """Fetch new incidents from Rekt News RSS feed."""
    print("\n" + "=" * 60)
    print("🚨 Rekt News — Incident Monitor")
    print("=" * 60)

    if not feedparser:
        print("  ❌ feedparser not installed.")
        return []

    try:
        feed = feedparser.parse(config.REKT_NEWS_RSS)
    except Exception as e:
        print(f"  ❌ RSS fetch failed: {e}")
        return []

    seen = state.get("seen_rekt", [])
    new_incidents = []

    for entry in feed.entries[:10]:  # Check last 10 entries
        entry_id = entry.get("id", entry.get("link", ""))
        if entry_id in seen:
            continue

        title = entry.get("title", "")
        summary = entry.get("summary", "")[:500]
        link = entry.get("link", "")
        published = entry.get("published", "")

        new_incidents.append({
            "title": title,
            "summary": summary,
            "link": link,
            "published": published,
            "source": "Rekt News",
        })

        seen.append(entry_id)
        print(f"  🚨 New: {title}")

    # Keep only last 100 seen IDs
    state["seen_rekt"] = seen[-100:]

    if not new_incidents:
        print("  ✅ No new incidents")

    return new_incidents


# ================================================================
#  AI Incident Analysis & Outreach Drafting
# ================================================================

INCIDENT_ANALYSIS_PROMPT = """You are analyzing a blockchain security incident for a security audit firm (Verichains).

Your job:
1. Identify the affected project name
2. Categorize the incident (DeFi-DEX, DeFi-Lending, DeFi-Bridge, DeFi-Yield, GameFi, L1, L2, Oracle, Wallet, etc.)
3. Estimate the amount lost (if mentioned)
4. Identify the root cause (smart contract bug, oracle manipulation, bridge exploit, private key compromise, etc.)
5. Draft a short, professional outreach message that Verichains can send to COMPETITOR protocols in the same category

The outreach should:
- Reference the incident professionally (not fear-mongering, but fact-based urgency)
- Briefly explain the attack vector
- Position Verichains as capable of auditing for similar vulnerabilities
- Be concise (3-4 sentences max)
- Tone: Professional, helpful, not salesy

OUTPUT FORMAT (strict JSON):
{
    "project_name": "Protocol Z",
    "category": "DeFi-Bridge",
    "amount_lost": "$15M",
    "root_cause": "Signature verification bypass in bridge relayer",
    "severity": "critical",
    "outreach_draft": "Hi team, following the recent exploit of Protocol Z ($15M lost due to signature verification bypass), we wanted to reach out. This type of vulnerability is common in cross-chain bridges and could affect similar architectures. Verichains specializes in deep cryptography and bridge security audits — we'd be happy to do a quick review of your signing logic. Would you be open to a brief call?",
    "similar_categories": ["DeFi-Bridge", "Cross-chain", "Interoperability"]
}

Always respond with valid JSON only."""


def analyze_incident(incident: dict) -> dict | None:
    """Use AI to analyze an incident and draft outreach."""
    if not ai_scorer.client:
        print("  [AI] ⚠️  OpenAI not configured. Skipping analysis.")
        return None

    prompt = f"""Analyze this blockchain security incident:

Title: {incident['title']}
Summary: {incident['summary']}
Source: {incident['source']}
Link: {incident.get('link', 'N/A')}
Published: {incident.get('published', 'N/A')}

Provide analysis and draft outreach message."""

    try:
        response = ai_scorer.client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": INCIDENT_ANALYSIS_PROMPT},
                {"role": "user", "content": prompt},
            ],
            max_tokens=800,
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"  [AI] ❌ Analysis failed: {e}")
        return None


# ================================================================
#  Main Pipeline
# ================================================================

def process_incidents(incidents: list[dict]):
    """Analyze incidents, find targets, and send alerts."""
    if not incidents:
        return

    print(f"\n[Pipeline] 🧠 Analyzing {len(incidents)} incident(s)...")

    for incident in incidents:
        print(f"\n  Processing: {incident['title'][:60]}...")

        # AI analysis
        analysis = analyze_incident(incident)
        if not analysis:
            continue

        category = analysis.get("category", "")
        print(f"    Category: {category}")
        print(f"    Root cause: {analysis.get('root_cause', 'Unknown')}")
        print(f"    Amount lost: {analysis.get('amount_lost', 'Unknown')}")

        # Find similar projects from watchlist
        similar_categories = analysis.get("similar_categories", [category])
        targets = []
        for cat in similar_categories:
            cat_targets = airtable_client.get_watchlist_by_category(cat)
            targets.extend(cat_targets)

        # Deduplicate
        seen_names = set()
        unique_targets = []
        for t in targets:
            if t["name"] not in seen_names:
                unique_targets.append(t)
                seen_names.add(t["name"])
        targets = unique_targets[:10]  # Max 10 targets

        target_names = [t["name"] for t in targets]
        if not target_names:
            # If no watchlist targets, just alert about the incident
            target_names = ["(Add similar protocols to Watchlist for auto-targeting)"]

        print(f"    Targets: {', '.join(target_names[:5])}")

        # Send Telegram alert
        telegram_bot.alert_incident({
            "name": analysis.get("project_name", incident["title"]),
            "amount_lost": analysis.get("amount_lost", "Unknown"),
            "category": category,
            "root_cause": analysis.get("root_cause", "Unknown"),
            "targets": target_names,
            "outreach_draft": analysis.get("outreach_draft", ""),
        })

        time.sleep(1)


def main():
    print("🚨 Verichains LeadHunter — Incident Radar")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Load state
    state = load_state()

    # Fetch incidents
    incidents = fetch_rekt_news(state)

    # Process
    process_incidents(incidents)

    # Save state
    save_state(state)

    # Summary
    print("\n" + "=" * 60)
    print("📊 INCIDENT RADAR SUMMARY")
    print("=" * 60)
    print(f"  🚨 New incidents: {len(incidents)}")
    print()
    print("✅ Incident radar complete!")


if __name__ == "__main__":
    main()
