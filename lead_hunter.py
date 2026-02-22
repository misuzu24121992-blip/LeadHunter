from __future__ import annotations

"""
Verichains LeadHunter — Lead Hunter Script
Discovers new blockchain projects from:
  1. DeFiLlama (new protocols with TVL)
  2. RootData (new funding rounds)
  3. DoraHacks / ETHGlobal (hackathon winners) — Phase 4

Scores them via AI and pushes HOT/WARM leads to Airtable + Telegram.

Usage:
    python lead_hunter.py              # Run all sources
    python lead_hunter.py defillama    # DeFiLlama only
    python lead_hunter.py rootdata     # RootData only
"""

import sys
import json
import time
from datetime import datetime, timedelta, timezone

import requests

import config
import ai_scorer
import airtable_client
import telegram_bot


# ================================================================
#  DeFiLlama — New Protocols Detector
# ================================================================

def fetch_defillama_new_protocols(days_back: int = None) -> list[dict]:
    """
    Fetch protocols listed on DeFiLlama in the last N days.

    Returns list of raw protocol data dicts.
    """
    days_back = days_back or config.DEFILLAMA_NEW_PROTOCOL_DAYS
    cutoff_ts = int((datetime.now(timezone.utc) - timedelta(days=days_back)).timestamp())

    print(f"[DeFiLlama] 🔍 Fetching protocols listed in the last {days_back} days...")

    try:
        resp = requests.get(f"{config.DEFILLAMA_API_BASE}/protocols", timeout=30)
        resp.raise_for_status()
        protocols = resp.json()
    except Exception as e:
        print(f"[DeFiLlama] ❌ API failed: {e}")
        return []

    new_protocols = []
    for p in protocols:
        listed_at = p.get("listedAt", 0)
        if listed_at and listed_at >= cutoff_ts:
            new_protocols.append({
                "name": p.get("name") or "Unknown",
                "category": p.get("category") or "N/A",
                "chains": p.get("chains") or [],
                "tvl": p.get("tvl") or 0,
                "change_1d": p.get("change_1d") or 0,
                "change_7d": p.get("change_7d") or 0,
                "listed_at": datetime.fromtimestamp(listed_at, timezone.utc).strftime("%Y-%m-%d"),
                "url": p.get("url") or "",
                "twitter": p.get("twitter") or "",
                "github": p.get("github") or "",
                "description": p.get("description") or "",
                "slug": p.get("slug") or "",
                "forked_from": p.get("forkedFrom") or [],
            })

    print(f"[DeFiLlama] ✅ Found {len(new_protocols)} new protocols")
    return new_protocols


def format_defillama_for_scoring(protocol: dict) -> str:
    """Format DeFiLlama protocol data for AI scoring."""
    chains_list = protocol.get("chains") or []
    chains = ", ".join(chains_list[:5]) or "Unknown"
    forked_list = protocol.get("forked_from") or []
    forked = ", ".join(forked_list) if forked_list else ""

    tvl = protocol.get("tvl") or 0
    change_1d = protocol.get("change_1d") or 0
    change_7d = protocol.get("change_7d") or 0

    return f"""
Project: {protocol.get('name', 'Unknown')}
Category: {protocol.get('category') or 'N/A'}
Chains: {chains}
TVL: ${tvl:,.0f}
TVL Change 1d: {change_1d:.1f}%
TVL Change 7d: {change_7d:.1f}%
Listed on DeFiLlama: {protocol.get('listed_at') or 'Unknown'}
Website: {protocol.get('url') or 'N/A'}
Twitter: {protocol.get('twitter') or 'N/A'}
GitHub: {protocol.get('github') or 'N/A'}
Description: {protocol.get('description') or 'N/A'}
Forked From: {forked if forked else 'Original / Unknown'}
""".strip()


# ================================================================
#  RootData — Funding Rounds Tracker
# ================================================================

def fetch_rootdata_funding_rounds(days_back: int = 7) -> list[dict]:
    """
    Fetch recent funding rounds from RootData API.

    Note: RootData API may require authentication.
    Falls back to graceful error if API not available.
    """
    print(f"[RootData] 🔍 Fetching funding rounds from the last {days_back} days...")

    if not config.ROOTDATA_API_KEY:
        print("[RootData] ⚠️  API key not configured. Skipping.")
        print("[RootData] 💡 Get API key from https://www.rootdata.com/")
        return []

    headers = {
        "apikey": config.ROOTDATA_API_KEY,
        "Content-Type": "application/json",
        "language": "en",
    }

    try:
        resp = requests.post(
            config.ROOTDATA_API_BASE,
            headers=headers,
            json={"page": 1, "page_size": 50},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("result") != 200:
            print(f"[RootData] ⚠️  API returned: {data.get('msg', 'Unknown error')}")
            return []

        rounds = data.get("data", {}).get("list", [])
    except Exception as e:
        print(f"[RootData] ❌ API failed: {e}")
        return []

    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)
    new_rounds = []

    for r in rounds:
        try:
            round_date_str = r.get("invest_date", "")
            if round_date_str:
                round_date = datetime.strptime(round_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                if round_date < cutoff_date:
                    continue
        except (ValueError, TypeError):
            pass

        investors = r.get("invest_map", [])
        investor_names = [inv.get("name", "") for inv in investors] if investors else []

        new_rounds.append({
            "name": r.get("name", "Unknown"),
            "logo": r.get("logo", ""),
            "round": r.get("round_name", "Unknown"),
            "amount": r.get("amount", "Undisclosed"),
            "valuation": r.get("valuation", "N/A"),
            "invest_date": round_date_str,
            "investors": investor_names,
            "category": r.get("tag_relation", []),
            "description": r.get("introduction", ""),
        })

    print(f"[RootData] ✅ Found {len(new_rounds)} recent funding rounds")
    return new_rounds


def format_rootdata_for_scoring(funding_round: dict) -> str:
    """Format RootData funding round for AI scoring."""
    investors_str = ", ".join(funding_round.get("investors", [])[:10])
    categories = funding_round.get("category", [])
    cat_str = ", ".join([c.get("name", "") for c in categories] if isinstance(categories, list) and categories and isinstance(categories[0], dict) else [str(c) for c in categories])

    return f"""
Project: {funding_round['name']}
Funding Round: {funding_round.get('round', 'Unknown')}
Amount Raised: {funding_round.get('amount', 'Undisclosed')}
Valuation: {funding_round.get('valuation', 'N/A')}
Date: {funding_round.get('invest_date', 'Unknown')}
Investors: {investors_str if investors_str else 'Undisclosed'}
Categories/Tags: {cat_str if cat_str else 'N/A'}
Description: {funding_round.get('description', 'N/A')}
""".strip()


# ================================================================
#  Main Pipeline
# ================================================================

def process_leads(raw_leads: list[str], source: str, existing_names: list[str]) -> list[dict]:
    """
    Score leads via AI, filter by threshold, push to Airtable + Telegram.

    Args:
        raw_leads: List of formatted strings for scoring
        source: Source name
        existing_names: List of project names already in pipeline (for dedup)

    Returns:
        List of scored leads that were actionable
    """
    if not raw_leads:
        print(f"[{source}] No new leads to process.")
        return []

    print(f"\n[Pipeline] 🧠 Scoring {len(raw_leads)} leads from {source}...")

    scored_leads = []
    for i, lead_text in enumerate(raw_leads):
        print(f"  Scoring {i+1}/{len(raw_leads)}...", end=" ")
        result = ai_scorer.score_lead(lead_text, source)
        if result:
            scored_leads.append(result)
            print(f"✅ {result.get('name', '?')} → {result.get('score', 0)}/100 ({result.get('priority', '?')})")
        else:
            print("❌ Failed")
        time.sleep(0.5)  # Rate limiting

    # Filter and dedup
    actionable = []
    for lead in scored_leads:
        name = lead.get("name", "")
        score = lead.get("score", 0)

        # Dedup check
        if name.lower() in [n.lower() for n in existing_names]:
            print(f"  ⏭️  {name} already in pipeline. Skipping.")
            continue

        # Only process WARM and above
        if score < config.SCORE_MONITOR_THRESHOLD:
            print(f"  ⬇️  {name} (Score: {score}) — too low, skipping.")
            continue

        # Push to Airtable
        airtable_client.push_lead(lead)

        # Telegram alert for HOT and WARM
        if score >= config.SCORE_HOT_THRESHOLD:
            telegram_bot.alert_new_lead(lead)
        elif score >= config.SCORE_WARM_THRESHOLD:
            telegram_bot.alert_new_lead(lead)

        actionable.append(lead)

    return actionable


def run_defillama(existing_names: list[str]) -> list[dict]:
    """Run DeFiLlama new protocol detection pipeline."""
    print("\n" + "=" * 60)
    print("📡 DeFiLlama — New Protocol Detection")
    print("=" * 60)

    protocols = fetch_defillama_new_protocols()
    if not protocols:
        return []

    # Format for scoring
    raw_leads = [format_defillama_for_scoring(p) for p in protocols]
    return process_leads(raw_leads, "DeFiLlama", existing_names)


def run_rootdata(existing_names: list[str]) -> list[dict]:
    """Run RootData funding round detection pipeline."""
    print("\n" + "=" * 60)
    print("💰 RootData — Funding Rounds Detection")
    print("=" * 60)

    rounds = fetch_rootdata_funding_rounds()
    if not rounds:
        return []

    # Format for scoring
    raw_leads = [format_rootdata_for_scoring(r) for r in rounds]
    return process_leads(raw_leads, "RootData", existing_names)


def main():
    """Main entry point."""
    print("🚀 Verichains LeadHunter — Starting lead hunt...")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Determine which sources to run
    sources = sys.argv[1:] if len(sys.argv) > 1 else ["defillama", "rootdata"]

    # Get existing pipeline for dedup
    existing_names = airtable_client.get_pipeline_projects()
    print(f"📋 {len(existing_names)} projects already in pipeline")

    all_leads = []

    if "defillama" in sources:
        leads = run_defillama(existing_names)
        all_leads.extend(leads)
        # Update existing names for cross-source dedup
        existing_names.extend([l.get("name", "") for l in leads])

    if "rootdata" in sources:
        leads = run_rootdata(existing_names)
        all_leads.extend(leads)

    # Summary
    print("\n" + "=" * 60)
    print("📊 SUMMARY")
    print("=" * 60)
    hot = [l for l in all_leads if l.get("score", 0) >= config.SCORE_HOT_THRESHOLD]
    warm = [l for l in all_leads if config.SCORE_WARM_THRESHOLD <= l.get("score", 0) < config.SCORE_HOT_THRESHOLD]
    monitor = [l for l in all_leads if config.SCORE_MONITOR_THRESHOLD <= l.get("score", 0) < config.SCORE_WARM_THRESHOLD]

    print(f"  🔴 HOT leads: {len(hot)}")
    for l in hot:
        print(f"     → {l.get('name')} ({l.get('score')}/100) - {l.get('category')}")
    print(f"  🟡 WARM leads: {len(warm)}")
    for l in warm:
        print(f"     → {l.get('name')} ({l.get('score')}/100) - {l.get('category')}")
    print(f"  🟢 MONITOR: {len(monitor)}")
    print(f"  Total actionable: {len(all_leads)}")
    print()

    # Send daily digest summary if there are leads
    if all_leads:
        digest = (
            f"📊 <b>LeadHunter Daily Digest</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔴 HOT: {len(hot)} | 🟡 WARM: {len(warm)} | 🟢 MONITOR: {len(monitor)}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
        )
        for l in hot + warm:
            digest += f"• <b>{l.get('name')}</b> ({l.get('score')}/100) — {l.get('category')} — {l.get('source')}\n"

        telegram_bot.send_message(digest)

    print("✅ Lead hunt complete!")


if __name__ == "__main__":
    main()
