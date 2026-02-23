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

def _heuristic_score(protocol: dict) -> dict:
    """Simple heuristic scoring when AI is not available. Includes breakdown."""
    tvl = protocol.get("tvl") or 0
    category = (protocol.get("category") or "").lower()
    name = protocol.get("name") or "Unknown"
    description = (protocol.get("description") or "").lower()
    change_7d = protocol.get("change_7d") or 0

    # Build breakdown
    breakdown = {}
    base = 30
    breakdown["Base Score"] = {"points": base, "max": 30, "reason": "Starting baseline for all protocols"}

    # TVL signals
    tvl_pts = 0
    if tvl > 50_000_000:
        tvl_pts = 25
        tvl_reason = f"Very high TVL (${tvl:,.0f})"
    elif tvl > 10_000_000:
        tvl_pts = 20
        tvl_reason = f"Strong TVL (${tvl:,.0f})"
    elif tvl > 1_000_000:
        tvl_pts = 15
        tvl_reason = f"Moderate TVL (${tvl:,.0f})"
    elif tvl > 100_000:
        tvl_pts = 10
        tvl_reason = f"Small TVL (${tvl:,.0f})"
    else:
        tvl_reason = f"Very low TVL (${tvl:,.0f})"
    breakdown["TVL"] = {"points": tvl_pts, "max": 25, "reason": tvl_reason}

    # Category relevance
    cat_pts = 0
    high_value_cats = ["dexs", "lending", "bridge", "derivatives", "cdp", "yield", "liquid staking"]
    mid_value_cats = ["defi", "staking", "rwa", "gaming", "nft"]
    if any(c in category for c in high_value_cats):
        cat_pts = 15
        cat_reason = f"High-value category ({protocol.get('category')})"
    elif any(c in category for c in mid_value_cats):
        cat_pts = 10
        cat_reason = f"Mid-value category ({protocol.get('category')})"
    else:
        cat_reason = f"Low-value category ({protocol.get('category') or 'Other'})"
    breakdown["Category Relevance"] = {"points": cat_pts, "max": 15, "reason": cat_reason}

    # Smart contract signals
    desc_pts = 0
    if any(kw in description for kw in ["smart contract", "defi", "protocol", "vault", "pool", "swap"]):
        desc_pts = 5
        desc_reason = "Description contains smart contract keywords"
    else:
        desc_reason = "No smart contract keywords in description"
    breakdown["Description Signals"] = {"points": desc_pts, "max": 5, "reason": desc_reason}

    # Growing TVL
    growth_pts = 0
    if isinstance(change_7d, (int, float)) and change_7d > 50:
        growth_pts = 10
        growth_reason = f"Strong growth ({change_7d:.1f}% in 7d)"
    elif isinstance(change_7d, (int, float)) and change_7d > 10:
        growth_pts = 5
        growth_reason = f"Moderate growth ({change_7d:.1f}% in 7d)"
    else:
        growth_reason = f"Low/negative growth ({change_7d:.1f}% in 7d)" if isinstance(change_7d, (int, float)) else "No growth data"
    breakdown["7d Growth"] = {"points": growth_pts, "max": 10, "reason": growth_reason}

    # Unknown factors (AI would fill these)
    breakdown["Funding & Backers"] = {"points": 0, "max": 15, "reason": "Unknown — requires AI scoring"}
    breakdown["Audit Status"] = {"points": 0, "max": 10, "reason": "Unknown — requires AI scoring"}

    score = min(base + tvl_pts + cat_pts + desc_pts + growth_pts, 100)

    # Set priority
    if score >= 75:
        priority = "HOT"
    elif score >= 55:
        priority = "WARM"
    elif score >= 40:
        priority = "MONITOR"
    else:
        priority = "LOW"

    # Build links from DeFiLlama data
    slug = protocol.get("slug") or ""
    twitter = protocol.get("twitter") or ""
    github_list = protocol.get("github") or []
    github_url = github_list[0] if isinstance(github_list, list) and github_list else (github_list if isinstance(github_list, str) else "")

    return {
        "name": name,
        "category": protocol.get("category") or "Other",
        "score": score,
        "priority": priority,
        "source": "DeFiLlama",
        "signals": [f"TVL: ${tvl:,.0f}", f"7d change: {change_7d:.1f}%"],
        "summary": f"New protocol on DeFiLlama. {protocol.get('description') or 'No description.'}",
        "funding": f"TVL: ${tvl:,.0f}",
        "tech": ", ".join((protocol.get("chains") or [])[:3]) or "Unknown chain",
        "audit_status": "Unknown — needs review",
        "pitch_services": ["Smart Contract Audit"],
        "score_breakdown": breakdown,
        "scored_by": "heuristic",
        "lead_group": "A",
        "listed_at": protocol.get("listed_at") or "",
        "website_url": protocol.get("url") or "",
        "twitter_url": f"https://x.com/{twitter}" if twitter else "",
        "github_url": github_url,
        "defillama_url": f"https://defillama.com/protocol/{slug}" if slug else "",
    }


def _run_lead_scan():
    """Run lead_hunter scan — heuristic scoring only.
    AI scoring is handled separately by Antigravity via /api/leads/bulk-score."""
    import lead_hunter
    import database as db

    log_id = db.start_scan_log("lead_hunter")
    try:
        existing = db.get_lead_names()
        protocols = lead_hunter.fetch_defillama_new_protocols()

        # Heuristic scoring — fast, no API needed
        scored = []
        print(f"[Scan] Heuristic scoring {len(protocols)} protocols...")
        for protocol in protocols:
            scored.append(_heuristic_score(protocol))

        hot = warm = pushed = 0
        existing_lower = [n.lower() for n in existing]
        for lead in scored:
            name = lead.get("name", "")
            score = lead.get("score", 0)
            if name.lower() in existing_lower:
                continue
            if score < 40:
                continue
            if db.insert_lead(lead):
                pushed += 1
                if score >= 75:
                    hot += 1
                elif score >= 55:
                    warm += 1
                existing_lower.append(name.lower())

        db.complete_scan_log(log_id, pushed, hot, warm,
                            f"Found {len(protocols)} protocols (heuristic), pushed {pushed}")
        return {"pushed": pushed, "hot": hot, "warm": warm, "total_found": len(protocols), "mode": "heuristic"}
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
        watchlist = db.get_watchlist()
        if not watchlist:
            db.complete_scan_log(log_id, 0, 0, 0, "No projects in watchlist")
            return {"changes": 0}

        state = upgrade_watcher.load_state()
        changes = upgrade_watcher.run_github_monitor(watchlist, state)
        snapshot = upgrade_watcher.check_snapshot_proposals(watchlist, state)
        changes.extend(snapshot)
        meaningful = upgrade_watcher.process_changes(changes)
        upgrade_watcher.save_state(state)

        db.complete_scan_log(log_id, len(meaningful), 0, 0, f"Raw: {len(changes)}, Meaningful: {len(meaningful)}")
        return {"raw_changes": len(changes), "meaningful": len(meaningful)}
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
        else:
            raise HTTPException(400, f"Unknown scan type: {scan_type}")
        return {"ok": True, "result": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        _scan_lock.release()


if __name__ == "__main__":
    print("🚀 Verichains LeadHunter — Starting web server...")
    print("📊 Dashboard: http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
