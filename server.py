from __future__ import annotations

"""
Verichains LeadHunter — FastAPI Server
Serves the web dashboard and API endpoints.

Usage:
    python server.py
    → Opens http://localhost:8000
"""

import os
import json
import time
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

import database as db

# Lazy imports for scan functions
_scan_lock = threading.Lock()

def _antigravity_score(protocol: dict) -> dict:
    """
    Antigravity auto-scoring using 6-dimension rubric.
    Uses DeFiLlama data + audit enrichment for comprehensive scoring.
    """
    tvl = protocol.get("tvl") or 0
    category = (protocol.get("category") or "").lower()
    name = protocol.get("name") or "Unknown"
    description = (protocol.get("description") or "").lower()
    change_7d = protocol.get("change_7d") or 0
    audits = protocol.get("audits") or "0"
    audit_links = protocol.get("audit_links") or []
    forked_from = protocol.get("forked_from") or []
    chains = protocol.get("chains") or []

    # Detect non-protocol tokens (RWA stocks, wrapped tokens)
    non_protocol_keywords = ["stock", "tokenized stock", "equity", "share",
                              "represents", "wrapped token", "synthetic stock"]
    is_non_protocol = (category == "rwa" and
                       any(kw in description for kw in non_protocol_keywords))

    breakdown = {}

    # 1. Audit Need (max 25)
    # Uses multi-source audit check results (set by _run_lead_scan)
    audit_result = protocol.get("_audit_result") or {}
    has_audit = audit_result.get("has_audit", False)

    if is_non_protocol:
        audit_pts = 2
        audit_reason = "Non-protocol token (RWA/stock) — audit not applicable"
    elif has_audit:
        audit_pts = 3
        audit_source = audit_result.get("audit_source", "")
        audit_reason = f"Audited (found via {audit_source})"
    else:
        # Checked DeFiLlama, GitHub, website, docs — no audit found
        if tvl > 1_000_000:
            audit_pts = 22
            audit_reason = f"No audit found (checked all sources). TVL ${tvl:,.0f} — strong opportunity"
        elif tvl > 100_000:
            audit_pts = 18
            audit_reason = f"No audit found (checked all sources). TVL ${tvl:,.0f}"
        elif tvl > 10_000:
            audit_pts = 12
            audit_reason = f"No audit found. TVL ${tvl:,.0f}"
        else:
            audit_pts = 5
            audit_reason = f"No audit found. Negligible TVL (${tvl:,.0f})"
    breakdown["Audit Need"] = {"points": audit_pts, "max": 25, "reason": audit_reason}

    # 2. Funding & Budget (max 15) — TVL as proxy for budget capacity
    if tvl > 50_000_000:
        fund_pts = 14
        fund_reason = f"Very high TVL (${tvl:,.0f}) — strong budget"
    elif tvl > 10_000_000:
        fund_pts = 12
        fund_reason = f"High TVL (${tvl:,.0f}) — good budget"
    elif tvl > 1_000_000:
        fund_pts = 9
        fund_reason = f"Moderate TVL (${tvl:,.0f})"
    elif tvl > 100_000:
        fund_pts = 5
        fund_reason = f"Small TVL (${tvl:,.0f})"
    elif tvl > 10_000:
        fund_pts = 3
        fund_reason = f"Very small TVL (${tvl:,.0f})"
    else:
        fund_pts = 1
        fund_reason = f"Negligible TVL (${tvl:,.0f})"
    breakdown["Funding & Budget"] = {"points": fund_pts, "max": 15, "reason": fund_reason}

    # 3. Category Fit (max 15) — Verichains service alignment
    if is_non_protocol:
        cat_pts = 1
        cat_reason = f"Non-protocol token ({protocol.get('category')}) — not a smart contract target"
    else:
        high_fit = ["bridge", "cross chain", "lending", "cdp", "derivatives", "liquid staking"]
        good_fit = ["dexs", "yield", "yield aggregator", "staking pool", "rwa"]
        mid_fit = ["staking", "gaming", "nft", "launchpad"]
        if any(c in category for c in high_fit):
            cat_pts = 14
            cat_reason = f"High Verichains fit ({protocol.get('category')})"
        elif any(c in category for c in good_fit):
            cat_pts = 10
            cat_reason = f"Good Verichains fit ({protocol.get('category')})"
        elif any(c in category for c in mid_fit):
            cat_pts = 6
            cat_reason = f"Moderate fit ({protocol.get('category')})"
        else:
            cat_pts = 3
            cat_reason = f"Low fit ({protocol.get('category') or 'Other'})"
    breakdown["Category Fit"] = {"points": cat_pts, "max": 15, "reason": cat_reason}

    # 4. Growth & Timing (max 10)
    growth_pts = 0
    if isinstance(change_7d, (int, float)) and change_7d > 100:
        growth_pts = 9
        growth_reason = f"Explosive growth ({change_7d:.1f}% in 7d)"
    elif isinstance(change_7d, (int, float)) and change_7d > 30:
        growth_pts = 7
        growth_reason = f"Strong growth ({change_7d:.1f}% in 7d)"
    elif isinstance(change_7d, (int, float)) and change_7d > 10:
        growth_pts = 5
        growth_reason = f"Moderate growth ({change_7d:.1f}% in 7d)"
    elif isinstance(change_7d, (int, float)) and change_7d > 0:
        growth_pts = 3
        growth_reason = f"Slight growth ({change_7d:.1f}% in 7d)"
    else:
        growth_pts = 1
        growth_reason = f"Flat/declining ({change_7d:.1f}% in 7d)" if isinstance(change_7d, (int, float)) else "No growth data"
    breakdown["Growth & Timing"] = {"points": growth_pts, "max": 10, "reason": growth_reason}

    # 5. Verichains Moat (max 5) — ZK, crypto, cross-chain = specialty
    moat_pts = 1
    moat_reason = "Standard protocol"
    moat_keywords = {"zk": 4, "zero knowledge": 4, "bridge": 3, "cross-chain": 3,
                     "cryptography": 4, "mpc": 4, "threshold": 3, "rollup": 3}
    for kw, pts in moat_keywords.items():
        if kw in description or kw in " ".join(chains).lower():
            moat_pts = max(moat_pts, pts)
            moat_reason = f"Verichains specialty: {kw}"
    breakdown["Verichains Moat"] = {"points": moat_pts, "max": 5, "reason": moat_reason}

    # 6. Base Score (max 30) — overall opportunity quality
    base = 5  # Minimum
    # Smart contract signals
    sc_keywords = ["smart contract", "defi", "protocol", "vault", "pool", "swap",
                   "staking", "lending", "liquidity", "amm", "erc-4626", "yield"]
    sc_match = sum(1 for kw in sc_keywords if kw in description)
    base += min(sc_match * 3, 12)  # Up to 12 pts from description

    # Forked = lower originality but proven model
    if forked_from:
        base += 5
        fork_note = f"Fork of {', '.join(forked_from[:2])} — proven model"
    else:
        base += 8
        fork_note = "Original protocol"

    # Multi-chain = more complex = more audit surface
    if len(chains) > 2:
        base += 3
    elif len(chains) > 1:
        base += 1

    base = min(base, 30)
    breakdown["Base Score"] = {"points": base, "max": 30, "reason": f"{fork_note}. SC keywords: {sc_match}"}

    # Total score
    score = min(audit_pts + fund_pts + cat_pts + growth_pts + moat_pts + base, 100)

    # Priority classification
    if score >= 75:
        priority = "HOT"
    elif score >= 55:
        priority = "WARM"
    elif score >= 40:
        priority = "MONITOR"
    else:
        priority = "LOW"

    # Build links
    slug = protocol.get("slug") or ""
    twitter = protocol.get("twitter") or ""
    github_list = protocol.get("github") or []
    github_url = github_list[0] if isinstance(github_list, list) and github_list else (github_list if isinstance(github_list, str) else "")

    # Audit status from multi-source check
    audit_result = protocol.get("_audit_result") or {}
    if is_non_protocol:
        audit_status = "N/A — Non-protocol RWA token"
    elif audit_result.get("has_audit"):
        audit_status = audit_result.get("audit_status", "✅ Audited")
    else:
        audit_status = audit_result.get("audit_status", "❌ No audit found")

    # Smart pitch services
    pitch = ["Smart Contract Audit"]
    if any(kw in category for kw in ["bridge", "cross chain"]):
        pitch.append("Cryptography Audit")
    if "zk" in description or "rollup" in description:
        pitch.append("Cryptography Audit (ZK)")
    if tvl > 1_000_000:
        pitch.append("Penetration Testing")

    # Summary
    desc_short = protocol.get("description") or "No description"
    if is_non_protocol:
        summary = f"{desc_short} TVL: ${tvl:,.0f}. Non-protocol RWA token — audit N/A."
    elif audit_result.get("has_audit"):
        summary = f"{desc_short} TVL: ${tvl:,.0f}. {audit_status}"
    else:
        summary = f"{desc_short} TVL: ${tvl:,.0f}. No audit found — potential opportunity."

    return {
        "name": name,
        "category": protocol.get("category") or "Other",
        "score": score,
        "priority": priority,
        "source": "DeFiLlama",
        "signals": [f"TVL: ${tvl:,.0f}", f"7d: {change_7d:.1f}%"],
        "summary": summary,
        "funding": f"TVL: ${tvl:,.0f}",
        "tech": ", ".join((chains)[:3]) or "Unknown chain",
        "audit_status": audit_status,
        "pitch_services": pitch,
        "score_breakdown": breakdown,
        "scored_by": "ai:antigravity",
        "lead_group": "A",
        "listed_at": protocol.get("listed_at") or "",
        "website_url": protocol.get("url") or "",
        "twitter_url": f"https://x.com/{twitter}" if twitter else "",
        "github_url": github_url,
        "defillama_url": f"https://defillama.com/protocol/{slug}" if slug else "",
    }


def _classify_audit(protocol: dict) -> str:
    """Classify audit status from DeFiLlama audits + audit_links fields."""
    audits = protocol.get("audits") or "0"
    audit_links = protocol.get("audit_links") or []

    if audits != "0" and audit_links:
        links_str = ", ".join(audit_links[:3])
        return f"✅ Audited — {len(audit_links)} report(s): {links_str}"
    elif audits != "0":
        return "✅ DeFiLlama reports audit exists (no links available)"
    else:
        return "⚠️ Unverified — DeFiLlama has no audit data. Run /score-leads for manual check."



def _run_lead_scan():
    """Run lead scan with Antigravity auto-scoring + multi-source audit checks."""
    import lead_hunter
    import database as db
    import audit_checker

    log_id = db.start_scan_log("lead_hunter")
    try:
        existing = db.get_lead_names()
        protocols = lead_hunter.fetch_defillama_new_protocols()

        # Enrich with audit data from DeFiLlama detail API
        protocols = lead_hunter.enrich_audit_from_defillama(protocols)

        # Multi-source audit check (handles Vercel/local internally)
        print(f"[Scan] 🔍 Running audit checks for {len(protocols)} protocols...")
        for i, protocol in enumerate(protocols):
            audit_result = audit_checker.check_audit(protocol)
            protocol["_audit_result"] = audit_result
            # Delay between protocols to avoid rate limiting (accuracy > speed)
            if i < len(protocols) - 1:
                time.sleep(20)

        # Antigravity scoring using audit results
        scored = []
        print(f"[Scan] 🧠 Antigravity scoring {len(protocols)} protocols...")
        for protocol in protocols:
            scored.append(_antigravity_score(protocol))


        hot = warm = pushed = 0
        existing_lower = [n.lower() for n in existing]
        for i, lead in enumerate(scored):
            name = lead.get("name", "")
            score = lead.get("score", 0)
            if name.lower() in existing_lower:
                continue
            if score < 40:
                continue
            lead_id = db.insert_lead(lead)
            if lead_id:
                pushed += 1
                if score >= 75:
                    hot += 1
                elif score >= 55:
                    warm += 1
                existing_lower.append(name.lower())

        summary = f"Found {len(protocols)} protocols, pushed {pushed} (heuristic)"
        print(f"[Scan] ✅ {summary}")
        print(f"[Scan] 💡 Run /score-leads for Antigravity AI scoring + audit verification")
        db.complete_scan_log(log_id, pushed, hot, warm, summary)
        return {"pushed": pushed, "hot": hot, "warm": warm, "total_found": len(protocols)}
    except Exception as e:
        import traceback
        traceback.print_exc()
        db.fail_scan_log(log_id, str(e))
        raise


def _run_upgrade_scan():
    """Run upgrade_watcher scan in background."""
    import upgrade_watcher
    import database as db

    log_id = db.start_scan_log("upgrade_watcher")
    try:
        watchlist_rows = db.get_watchlist()
        if not watchlist_rows:
            db.complete_scan_log(log_id, 0, 0, 0, "No projects in watchlist")
            return {"changes": 0}

        # Convert DB rows to dicts
        watchlist = [dict(r) if hasattr(r, 'keys') else r for r in watchlist_rows]
        result = upgrade_watcher.run_scan(watchlist, db_module=db)

        db.complete_scan_log(
            log_id,
            result.get("meaningful", 0),
            result.get("leads_created", 0),
            0,
            f"Raw: {result.get('raw_changes', 0)}, Meaningful: {result.get('meaningful', 0)}, Leads: {result.get('leads_created', 0)}"
        )
        return result
    except Exception as e:
        db.fail_scan_log(log_id, str(e))
        raise


def _run_incident_scan():
    """Run incident_radar scan in background."""
    import incident_radar
    import database as db

    log_id = db.start_scan_log("incident_radar")
    try:
        state = incident_radar.load_state()
        incidents = incident_radar.fetch_rekt_news(state)

        for inc in incidents:
            analysis = incident_radar.analyze_incident(inc)
            if analysis:
                analysis["title"] = inc.get("title", "")
                analysis["source"] = inc.get("source", "")
                analysis["link"] = inc.get("link", "")
                db.insert_incident(analysis)
                import telegram_bot
                telegram_bot.alert_incident(analysis)

        incident_radar.save_state(state)
        db.complete_scan_log(log_id, len(incidents), 0, 0, f"Found {len(incidents)} new incidents")
        return {"incidents": len(incidents)}
    except Exception as e:
        db.fail_scan_log(log_id, str(e))
        raise


# ============================
#  FastAPI App
# ============================

@asynccontextmanager
async def lifespan(app: FastAPI):
    db.get_conn()
    print("✅ Database initialized")
    yield

app = FastAPI(title="Verichains LeadHunter", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def root():
    return FileResponse(os.path.join(static_dir, "index.html"))


# ---- STATS ----
@app.get("/api/stats")
async def get_stats():
    return db.get_stats()


# ---- LEADS ----
@app.get("/api/leads")
async def get_leads(priority: str = None, stage: str = None,
                    category: str = None, search: str = None):
    return db.get_leads(priority=priority, stage=stage,
                        category=category, search=search)


@app.patch("/api/leads/{lead_id}")
async def update_lead(lead_id: int, updates: dict):
    if not db.update_lead(lead_id, updates):
        raise HTTPException(404, "Lead not found or no valid fields")
    return {"ok": True}


@app.delete("/api/leads/{lead_id}")
async def delete_lead(lead_id: int):
    db.delete_lead(lead_id)
    return {"ok": True}


@app.get("/api/leads/unscored")
async def get_unscored_leads():
    """Get leads that haven't been AI-scored yet (scored_by = 'heuristic').
    Used by Antigravity to fetch leads for deep analysis."""
    conn = db.get_conn()
    rows = conn.execute(
        "SELECT * FROM leads WHERE scored_by = 'heuristic' ORDER BY score DESC"
    ).fetchall()
    return {"leads": [dict(r) for r in rows], "count": len(rows)}


@app.post("/api/leads/bulk-score")
async def bulk_score_leads(payload: dict):
    """Accept AI-scored results from Antigravity and update leads in DB.
    Expects: { "scores": [ { "id": int, "score": int, "priority": str,
                              "summary": str, "score_breakdown": dict,
                              "audit_status": str, "pitch_services": list,
                              "funding": str, "tech": str } ] }"""
    scores = payload.get("scores", [])
    if not scores:
        raise HTTPException(400, "No scores provided")

    updated = 0
    conn = db.get_conn()
    for item in scores:
        lead_id = item.get("id")
        if not lead_id:
            continue

        # Build SET clause for all provided fields
        allowed = ["score", "priority", "summary", "audit_status",
                    "funding", "tech", "trigger_info", "lead_group",
                    "listed_at", "website_url", "twitter_url", "github_url", "defillama_url"]
        fields = []
        params = []

        for key in allowed:
            if key in item:
                fields.append(f"{key} = ?")
                params.append(item[key])

        # Handle JSON fields
        if "score_breakdown" in item:
            fields.append("score_breakdown = ?")
            params.append(json.dumps(item["score_breakdown"], ensure_ascii=False))

        if "pitch_services" in item:
            fields.append("pitch_services = ?")
            services = item["pitch_services"]
            params.append(", ".join(services) if isinstance(services, list) else services)

        # Always set scored_by and updated_at
        fields.append("scored_by = ?")
        params.append(item.get("scored_by", "ai:antigravity"))
        fields.append("updated_at = datetime('now')")

        if fields:
            params.append(lead_id)
            sql = f"UPDATE leads SET {', '.join(fields)} WHERE id = ?"
            conn.execute(sql, params)
            conn.commit()
            updated += 1

    return {"ok": True, "updated": updated, "total": len(scores)}


# ---- WATCHLIST ----
@app.get("/api/watchlist")
async def get_watchlist(category: str = None):
    return db.get_watchlist(category=category)


@app.post("/api/watchlist")
async def add_watchlist(project: dict):
    item_id = db.insert_watchlist(project)
    if not item_id:
        raise HTTPException(409, "Project already in watchlist")
    return {"ok": True, "id": item_id}


@app.patch("/api/watchlist/{item_id}")
async def update_watchlist(item_id: int, updates: dict):
    if not db.update_watchlist_item(item_id, updates):
        raise HTTPException(404, "Item not found")
    return {"ok": True}


@app.delete("/api/watchlist/{item_id}")
async def delete_watchlist(item_id: int):
    db.delete_watchlist_item(item_id)
    return {"ok": True}


# ---- INCIDENTS ----
@app.get("/api/incidents")
async def get_incidents():
    return db.get_incidents()


# ---- SCAN LOGS ----
@app.get("/api/scan-logs")
async def get_scan_logs():
    return db.get_scan_logs()


# ---- MANUAL SCAN TRIGGERS ----
@app.post("/api/run-scan/{scan_type}")
async def run_scan(scan_type: str):
    if not _scan_lock.acquire(blocking=False):
        raise HTTPException(409, "A scan is already running")

    try:
        if scan_type == "leads":
            result = _run_lead_scan()
        elif scan_type == "upgrades":
            result = _run_upgrade_scan()
        elif scan_type == "incidents":
            result = _run_incident_scan()
        elif scan_type == "rescore":
            result = _run_rescore()
        else:
            raise HTTPException(400, f"Unknown scan type: {scan_type}")
        return {"ok": True, "result": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        _scan_lock.release()


def _run_rescore():
    """Re-run audit checks and update scores for all existing leads."""
    import database as db
    import audit_checker
    import lead_hunter

    log_id = db.start_scan_log("rescore")
    try:
        leads = db.get_leads(limit=500)
        print(f"[Re-score] 🔄 Re-scoring {len(leads)} leads with audit checks...")

        # Fetch fresh bulk data from DeFiLlama for TVL, category etc.
        try:
            all_protocols = lead_hunter.fetch_defillama_new_protocols(days_back=365)
            protocols_by_name = {p.get('name', '').lower(): p for p in all_protocols}
        except Exception:
            protocols_by_name = {}

        updated = 0
        for lead in leads:
            lead_id = lead.get("id")
            name = lead.get("name", "")
            if not lead_id:
                continue

            # Build protocol dict from stored lead + fresh DeFiLlama data
            bulk = protocols_by_name.get(name.lower(), {})
            protocol = {
                "name": name,
                "tvl": bulk.get("tvl") or 0,
                "category": lead.get("category") or bulk.get("category") or "",
                "description": bulk.get("description") or lead.get("summary") or "",
                "change_7d": bulk.get("change_7d") or 0,
                "audits": bulk.get("audits") or "0",
                "audit_links": bulk.get("audit_links") or [],
                "forked_from": bulk.get("forkedFrom") or [],
                "chains": bulk.get("chains") or [],
                "github": bulk.get("github") or [],
                "url": lead.get("website_url") or bulk.get("url") or "",
                "slug": bulk.get("slug") or "",
                "twitter": bulk.get("twitter") or "",
                "listed_at": bulk.get("listedAt") or "",
            }

            # Run multi-source audit check
            audit_result = audit_checker.check_audit(protocol)
            protocol["_audit_result"] = audit_result

            # Re-score
            scored = _antigravity_score(protocol)

            # Update in DB
            import json
            db.update_lead(lead_id, {
                "score": scored["score"],
                "priority": scored["priority"],
                "audit_status": scored["audit_status"],
                "score_breakdown": json.dumps(scored.get("score_breakdown", {})),
                "scored_by": "ai:antigravity",
                "summary": scored["summary"],
                "pitch_services": ", ".join(scored.get("pitch_services", [])),
            })
            updated += 1
            print(f"  [{updated}/{len(leads)}] {name}: {scored['score']}pts ({scored['priority']}) — {scored['audit_status'][:60]}")

            # Delay between protocols to avoid rate limiting (accuracy > speed)
            if updated < len(leads):
                time.sleep(20)

        result = {"updated": updated, "total": len(leads)}
        import json as _json
        db.complete_scan_log(log_id, leads_found=updated, details=_json.dumps(result))
        print(f"[Re-score] ✅ Updated {updated}/{len(leads)} leads")
        return result

    except Exception as e:
        db.fail_scan_log(log_id, str(e))
        raise


# ---- SYNC (Local → Vercel) ----
@app.post("/api/sync-leads")
async def sync_leads(payload: dict):
    """Accept leads from local scan and upsert into Vercel DB."""
    leads = payload.get("leads", [])
    if not leads:
        return {"ok": False, "error": "No leads provided"}

    synced = 0
    existing = [n.lower() for n in db.get_lead_names()]

    for lead in leads:
        name = lead.get("name", "")
        if not name:
            continue

        if name.lower() in existing:
            # Update existing lead
            lead_id = lead.get("id")
            if lead_id:
                db.update_lead(lead_id, {
                    "score": lead.get("score", 0),
                    "priority": lead.get("priority", "MONITOR"),
                    "audit_status": lead.get("audit_status", ""),
                    "score_breakdown": lead.get("score_breakdown", "{}"),
                    "scored_by": lead.get("scored_by", "ai:antigravity"),
                    "summary": lead.get("summary", ""),
                    "pitch_services": lead.get("pitch_services", "[]"),
                })
                synced += 1
        else:
            # Insert new lead
            lead_id = db.insert_lead(lead)
            if lead_id:
                synced += 1
                existing.append(name.lower())

    return {"ok": True, "synced": synced, "total": len(leads)}


# ---- RESET ----
@app.post("/api/reset-db")
async def reset_db():
    """Reset database — wipe leads, scan_logs, incidents. Keep watchlist."""
    return db.reset_database()


if __name__ == "__main__":
    print("🚀 Verichains LeadHunter — Starting web server...")
    # Auto-cleanup stuck scans from previous server crash
    try:
        conn = db.get_conn()
        stuck = conn.execute("UPDATE scan_logs SET status='failed', details='Server restarted' WHERE status='running'")
        conn.commit()
        if stuck.rowcount > 0:
            print(f"🧹 Cleaned {stuck.rowcount} stuck scan(s) from previous session")
    except Exception:
        pass
    print("📊 Dashboard: http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)

