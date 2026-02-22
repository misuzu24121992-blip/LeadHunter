from __future__ import annotations

"""
Verichains LeadHunter — Database Layer
Supports: Turso (cloud), local SQLite, Vercel /tmp SQLite.
"""

import sqlite3
import os
import json
from datetime import datetime, timezone

# --- Connection config ---
TURSO_URL = os.environ.get("TURSO_DATABASE_URL")
TURSO_TOKEN = os.environ.get("TURSO_AUTH_TOKEN")
IS_VERCEL = os.environ.get("VERCEL")

# On Vercel, filesystem is read-only except /tmp
if IS_VERCEL:
    DATABASE_PATH = "/tmp/leads.db"
else:
    DATABASE_PATH = os.path.join(os.path.dirname(__file__), "leads.db")

_conn = None


def get_conn():
    """Get or create database connection. Supports Turso cloud or local SQLite."""
    global _conn
    if _conn is not None:
        return _conn

    if TURSO_URL and TURSO_TOKEN:
        # Use Turso cloud database (libsql SDK)
        try:
            import libsql
            _conn = libsql.connect(
                DATABASE_PATH,
                sync_url=TURSO_URL,
                auth_token=TURSO_TOKEN,
            )
            _conn.sync()
            print(f"[DB] ✅ Connected to Turso cloud: {TURSO_URL[:40]}...")
        except ImportError:
            print("[DB] ⚠️  libsql not installed, falling back to local SQLite")
            _conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        except Exception as e:
            print(f"[DB] ⚠️  Turso connection failed: {e}, falling back to local SQLite")
            _conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    else:
        # Local SQLite
        _conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        print(f"[DB] 📁 Using local SQLite: {DATABASE_PATH}")

    _conn.row_factory = sqlite3.Row
    try:
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA foreign_keys=ON")
    except Exception:
        pass  # Some Turso configs don't support PRAGMA

    init_tables(_conn)

    # Sync after creating tables (Turso)
    if TURSO_URL and TURSO_TOKEN:
        try:
            _conn.sync()
        except Exception:
            pass

    return _conn


def init_tables(conn: sqlite3.Connection):
    """Create all tables if they don't exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT DEFAULT 'Other',
            score INTEGER DEFAULT 0,
            priority TEXT DEFAULT 'LOW',
            source TEXT DEFAULT '',
            trigger_info TEXT DEFAULT '',
            stage TEXT DEFAULT 'Discovered',
            funding TEXT DEFAULT '',
            tech TEXT DEFAULT '',
            audit_status TEXT DEFAULT '',
            summary TEXT DEFAULT '',
            pitch_services TEXT DEFAULT '',
            score_breakdown TEXT DEFAULT '{}',
            contact_notes TEXT DEFAULT '',
            follow_up_date TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS watchlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            github_repo TEXT DEFAULT '',
            snapshot_space TEXT DEFAULT '',
            x_account TEXT DEFAULT '',
            category TEXT DEFAULT '',
            last_audit_date TEXT DEFAULT '',
            auditor TEXT DEFAULT '',
            client_type TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            project_name TEXT DEFAULT '',
            category TEXT DEFAULT '',
            amount_lost TEXT DEFAULT '',
            root_cause TEXT DEFAULT '',
            severity TEXT DEFAULT '',
            outreach_draft TEXT DEFAULT '',
            targets TEXT DEFAULT '[]',
            source TEXT DEFAULT '',
            link TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS scan_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_type TEXT NOT NULL,
            status TEXT DEFAULT 'running',
            leads_found INTEGER DEFAULT 0,
            hot_count INTEGER DEFAULT 0,
            warm_count INTEGER DEFAULT 0,
            details TEXT DEFAULT '',
            started_at TEXT DEFAULT (datetime('now')),
            completed_at TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_leads_priority ON leads(priority);
        CREATE INDEX IF NOT EXISTS idx_leads_stage ON leads(stage);
        CREATE INDEX IF NOT EXISTS idx_leads_score ON leads(score DESC);
    """)
    conn.commit()


# ============================
#  LEADS CRUD
# ============================

def insert_lead(lead: dict) -> int | None:
    """Insert a new lead. Returns ID or None if duplicate."""
    conn = get_conn()
    # Dedup by name
    existing = conn.execute("SELECT id FROM leads WHERE LOWER(name) = LOWER(?)", (lead.get("name", ""),)).fetchone()
    if existing:
        return None

    cursor = conn.execute("""
        INSERT INTO leads (name, category, score, priority, source, trigger_info, stage,
                          funding, tech, audit_status, summary, pitch_services, score_breakdown)
        VALUES (?, ?, ?, ?, ?, ?, 'Discovered', ?, ?, ?, ?, ?, ?)
    """, (
        lead.get("name", "Unknown"),
        lead.get("category", "Other"),
        lead.get("score", 0),
        lead.get("priority", "LOW"),
        lead.get("source", ""),
        ", ".join(lead.get("signals", [])),
        lead.get("funding", ""),
        lead.get("tech", ""),
        lead.get("audit_status", ""),
        lead.get("summary", ""),
        ", ".join(lead.get("pitch_services", [])),
        json.dumps(lead.get("score_breakdown", {}), ensure_ascii=False),
    ))
    conn.commit()
    return cursor.lastrowid


def get_leads(priority: str = None, stage: str = None, category: str = None,
              search: str = None, limit: int = 100) -> list[dict]:
    """Get leads with optional filters."""
    conn = get_conn()
    query = "SELECT * FROM leads WHERE 1=1"
    params = []

    if priority:
        query += " AND priority = ?"
        params.append(priority)
    if stage:
        query += " AND stage = ?"
        params.append(stage)
    if category:
        query += " AND category = ?"
        params.append(category)
    if search:
        query += " AND (LOWER(name) LIKE ? OR LOWER(summary) LIKE ?)"
        params.extend([f"%{search.lower()}%", f"%{search.lower()}%"])

    query += " ORDER BY score DESC, created_at DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def update_lead(lead_id: int, updates: dict) -> bool:
    """Update a lead's fields."""
    conn = get_conn()
    allowed = ["stage", "priority", "contact_notes", "follow_up_date", "category", "score"]
    fields = []
    params = []
    for key in allowed:
        if key in updates:
            fields.append(f"{key} = ?")
            params.append(updates[key])

    if not fields:
        return False

    fields.append("updated_at = datetime('now')")
    params.append(lead_id)
    conn.execute(f"UPDATE leads SET {', '.join(fields)} WHERE id = ?", params)
    conn.commit()
    return True


def delete_lead(lead_id: int) -> bool:
    conn = get_conn()
    conn.execute("DELETE FROM leads WHERE id = ?", (lead_id,))
    conn.commit()
    return True


def get_lead_names() -> list[str]:
    """Get all lead names for dedup."""
    conn = get_conn()
    rows = conn.execute("SELECT name FROM leads").fetchall()
    return [r["name"] for r in rows]


# ============================
#  WATCHLIST CRUD
# ============================

def insert_watchlist(project: dict) -> int | None:
    conn = get_conn()
    existing = conn.execute("SELECT id FROM watchlist WHERE LOWER(name) = LOWER(?)", (project.get("name", ""),)).fetchone()
    if existing:
        return None

    cursor = conn.execute("""
        INSERT INTO watchlist (name, github_repo, snapshot_space, x_account,
                              category, last_audit_date, auditor, client_type, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        project.get("name", ""),
        project.get("github_repo", ""),
        project.get("snapshot_space", ""),
        project.get("x_account", ""),
        project.get("category", ""),
        project.get("last_audit_date", ""),
        project.get("auditor", ""),
        project.get("client_type", ""),
        project.get("notes", ""),
    ))
    conn.commit()
    return cursor.lastrowid


def get_watchlist(category: str = None) -> list[dict]:
    conn = get_conn()
    if category:
        rows = conn.execute("SELECT * FROM watchlist WHERE category = ? ORDER BY name", (category,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM watchlist ORDER BY name").fetchall()
    return [dict(r) for r in rows]


def update_watchlist_item(item_id: int, updates: dict) -> bool:
    conn = get_conn()
    allowed = ["name", "github_repo", "snapshot_space", "x_account",
               "category", "last_audit_date", "auditor", "client_type", "notes"]
    fields = []
    params = []
    for key in allowed:
        if key in updates:
            fields.append(f"{key} = ?")
            params.append(updates[key])
    if not fields:
        return False
    params.append(item_id)
    conn.execute(f"UPDATE watchlist SET {', '.join(fields)} WHERE id = ?", params)
    conn.commit()
    return True


def delete_watchlist_item(item_id: int) -> bool:
    conn = get_conn()
    conn.execute("DELETE FROM watchlist WHERE id = ?", (item_id,))
    conn.commit()
    return True


# ============================
#  INCIDENTS
# ============================

def insert_incident(incident: dict) -> int:
    conn = get_conn()
    targets = json.dumps(incident.get("targets", []))
    cursor = conn.execute("""
        INSERT INTO incidents (title, project_name, category, amount_lost,
                              root_cause, severity, outreach_draft, targets, source, link)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        incident.get("title", ""),
        incident.get("project_name", ""),
        incident.get("category", ""),
        incident.get("amount_lost", ""),
        incident.get("root_cause", ""),
        incident.get("severity", ""),
        incident.get("outreach_draft", ""),
        targets,
        incident.get("source", ""),
        incident.get("link", ""),
    ))
    conn.commit()
    return cursor.lastrowid


def get_incidents(limit: int = 50) -> list[dict]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM incidents ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    results = []
    for r in rows:
        d = dict(r)
        try:
            d["targets"] = json.loads(d.get("targets", "[]"))
        except (json.JSONDecodeError, TypeError):
            d["targets"] = []
        results.append(d)
    return results


# ============================
#  SCAN LOGS
# ============================

def start_scan_log(scan_type: str) -> int:
    conn = get_conn()
    cursor = conn.execute("INSERT INTO scan_logs (scan_type) VALUES (?)", (scan_type,))
    conn.commit()
    return cursor.lastrowid


def complete_scan_log(log_id: int, leads_found: int = 0, hot: int = 0, warm: int = 0, details: str = ""):
    conn = get_conn()
    conn.execute("""
        UPDATE scan_logs SET status='completed', leads_found=?, hot_count=?,
               warm_count=?, details=?, completed_at=datetime('now')
        WHERE id = ?
    """, (leads_found, hot, warm, details, log_id))
    conn.commit()


def fail_scan_log(log_id: int, error: str):
    conn = get_conn()
    conn.execute("""
        UPDATE scan_logs SET status='failed', details=?, completed_at=datetime('now')
        WHERE id = ?
    """, (error, log_id))
    conn.commit()


def get_scan_logs(limit: int = 20) -> list[dict]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM scan_logs ORDER BY started_at DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


# ============================
#  STATS
# ============================

def get_stats() -> dict:
    conn = get_conn()
    total = conn.execute("SELECT COUNT(*) as c FROM leads").fetchone()["c"]
    hot = conn.execute("SELECT COUNT(*) as c FROM leads WHERE priority='HOT'").fetchone()["c"]
    warm = conn.execute("SELECT COUNT(*) as c FROM leads WHERE priority='WARM'").fetchone()["c"]
    monitor = conn.execute("SELECT COUNT(*) as c FROM leads WHERE priority='MONITOR'").fetchone()["c"]
    watchlist_count = conn.execute("SELECT COUNT(*) as c FROM watchlist").fetchone()["c"]
    incidents_count = conn.execute("SELECT COUNT(*) as c FROM incidents").fetchone()["c"]

    # Stage distribution
    stages = {}
    for row in conn.execute("SELECT stage, COUNT(*) as c FROM leads GROUP BY stage").fetchall():
        stages[row["stage"]] = row["c"]

    # Category distribution
    categories = {}
    for row in conn.execute("SELECT category, COUNT(*) as c FROM leads GROUP BY category").fetchall():
        categories[row["category"]] = row["c"]

    # Recent scan
    last_scan = conn.execute("SELECT * FROM scan_logs ORDER BY started_at DESC LIMIT 1").fetchone()

    return {
        "total_leads": total,
        "hot": hot,
        "warm": warm,
        "monitor": monitor,
        "watchlist_count": watchlist_count,
        "incidents_count": incidents_count,
        "stages": stages,
        "categories": categories,
        "last_scan": dict(last_scan) if last_scan else None,
    }
