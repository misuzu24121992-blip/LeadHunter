from __future__ import annotations

"""
Verichains LeadHunter — Database Layer
Supports: Turso HTTP API (cloud), local SQLite, Vercel /tmp SQLite.
"""

import sqlite3
import os
import json
import re
import requests as http_requests
from datetime import datetime, timezone

# --- Connection config ---
TURSO_URL = os.environ.get("TURSO_DATABASE_URL", "")
TURSO_TOKEN = os.environ.get("TURSO_AUTH_TOKEN", "")
IS_VERCEL = os.environ.get("VERCEL")

# On Vercel, filesystem is read-only except /tmp
if IS_VERCEL:
    DATABASE_PATH = "/tmp/leads.db"
else:
    DATABASE_PATH = os.path.join(os.path.dirname(__file__), "leads.db")


# ============================
#  Turso HTTP API Wrapper
# ============================

class TursoRow:
    """Row that supports both dict-like and index access."""
    def __init__(self, columns: list[str], values: list):
        self._columns = columns
        self._values = values
        self._map = dict(zip(columns, values))

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return self._map[key]

    def keys(self):
        return self._columns

    def __iter__(self):
        return iter(self._values)


class TursoCursor:
    """Cursor-like object for Turso HTTP results."""
    def __init__(self, columns: list[str], rows: list[list], lastrowid=None):
        self._columns = columns
        self._rows = [TursoRow(columns, r) for r in rows]
        self._pos = 0
        self.lastrowid = lastrowid

    def fetchone(self):
        if self._pos < len(self._rows):
            row = self._rows[self._pos]
            self._pos += 1
            return row
        return None

    def fetchall(self):
        return self._rows[self._pos:]


class TursoHTTPConnection:
    """
    sqlite3-compatible connection using Turso HTTP API.
    Uses POST /v2/pipeline with Bearer token auth.
    No native dependencies — pure Python + requests.
    """

    def __init__(self, url: str, token: str):
        # Convert libsql:// to https://
        self.base_url = url.replace("libsql://", "https://")
        self.pipeline_url = f"{self.base_url}/v2/pipeline"
        self.token = token
        self.row_factory = None  # Compatibility with sqlite3
        print(f"[DB] ✅ Connected to Turso cloud: {self.base_url[:50]}...")

    def _send(self, statements: list[dict]) -> list[dict]:
        """Send a pipeline of statements to Turso."""
        payload = {"requests": statements + [{"type": "close"}]}
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        resp = http_requests.post(self.pipeline_url, json=payload, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("results", [])

    def _convert_value(self, val):
        """Convert Turso response value to Python type."""
        if val is None:
            return None
        if isinstance(val, dict):
            t = val.get("type")
            v = val.get("value")
            if t == "null" or v is None:
                return None
            if t == "integer":
                return int(v)
            if t == "float":
                return float(v)
            if t == "text":
                return str(v)
            return v
        return val

    def _make_arg(self, val):
        """Convert Python value to Turso API arg format."""
        if val is None:
            return {"type": "null", "value": None}
        if isinstance(val, int):
            return {"type": "integer", "value": str(val)}
        if isinstance(val, float):
            return {"type": "float", "value": str(val)}
        return {"type": "text", "value": str(val)}

    def execute(self, sql: str, params=None) -> TursoCursor:
        """Execute a single SQL statement."""
        stmt = {"sql": sql.strip()}
        if params:
            stmt["args"] = [self._make_arg(p) for p in params]

        results = self._send([{"type": "execute", "stmt": stmt}])

        columns = []
        rows = []
        lastrowid = None

        if results and results[0].get("type") == "ok":
            result = results[0]["response"]["result"]
            columns = [c["name"] for c in result.get("cols", [])]
            rows = [
                [self._convert_value(v) for v in row]
                for row in result.get("rows", [])
            ]
            rid = result.get("last_insert_rowid")
            if rid:
                lastrowid = int(rid) if isinstance(rid, str) else rid
        elif results and results[0].get("type") == "error":
            err = results[0].get("error", {})
            msg = err.get("message", "Unknown Turso error")
            print(f"[DB] ❌ Turso error: {msg}")

        return TursoCursor(columns, rows, lastrowid)

    def executescript(self, script: str):
        """Execute multiple SQL statements (for CREATE TABLE etc)."""
        # Split by semicolons, filter empty
        statements = []
        for stmt in script.split(";"):
            stmt = stmt.strip()
            if stmt and not stmt.startswith("--"):
                statements.append({
                    "type": "execute",
                    "stmt": {"sql": stmt}
                })

        if statements:
            try:
                self._send(statements)
            except Exception as e:
                print(f"[DB] ⚠️  executescript partial error: {e}")

    def commit(self):
        """No-op — Turso auto-commits."""
        pass

    def close(self):
        """No-op."""
        pass


# ============================
#  Connection Factory
# ============================

_conn = None


def get_conn():
    """Get or create database connection. Turso HTTP or local SQLite."""
    global _conn
    if _conn is not None:
        return _conn

    if TURSO_URL and TURSO_TOKEN:
        try:
            _conn = TursoHTTPConnection(TURSO_URL, TURSO_TOKEN)
            init_tables(_conn)
            print("[DB] ✅ Turso tables initialized")
            return _conn
        except Exception as e:
            print(f"[DB] ⚠️  Turso connection failed: {e}, falling back to local SQLite")

    # Local SQLite fallback
    _conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    _conn.row_factory = sqlite3.Row
    _conn.execute("PRAGMA journal_mode=WAL")
    _conn.execute("PRAGMA foreign_keys=ON")
    init_tables(_conn)
    print(f"[DB] 📁 Using local SQLite: {DATABASE_PATH}")
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
            scored_by TEXT DEFAULT 'heuristic',
            lead_group TEXT DEFAULT 'A',
            listed_at TEXT DEFAULT '',
            website_url TEXT DEFAULT '',
            twitter_url TEXT DEFAULT '',
            github_url TEXT DEFAULT '',
            defillama_url TEXT DEFAULT '',
            contact_notes TEXT DEFAULT '',
            follow_up_date TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime'))
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
            proxy_contracts TEXT DEFAULT '{}',
            notes TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now','localtime'))
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
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS scan_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_type TEXT NOT NULL,
            status TEXT DEFAULT 'running',
            leads_found INTEGER DEFAULT 0,
            hot_count INTEGER DEFAULT 0,
            warm_count INTEGER DEFAULT 0,
            details TEXT DEFAULT '',
            started_at TEXT DEFAULT (datetime('now','localtime')),
            completed_at TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_leads_priority ON leads(priority);
        CREATE INDEX IF NOT EXISTS idx_leads_stage ON leads(stage);
        CREATE INDEX IF NOT EXISTS idx_leads_score ON leads(score DESC);
    """)
    conn.commit()

    # Migration: add scored_by column if missing (for existing data)
    try:
        conn.execute("ALTER TABLE leads ADD COLUMN scored_by TEXT DEFAULT 'heuristic'")
        conn.commit()
    except Exception:
        pass  # Column already exists

    # Migration: add lead_group column if missing
    try:
        conn.execute("ALTER TABLE leads ADD COLUMN lead_group TEXT DEFAULT 'A'")
        conn.commit()
    except Exception:
        pass  # Column already exists

    # Migration: add link/date columns if missing
    for col in ['listed_at', 'website_url', 'twitter_url', 'github_url', 'defillama_url']:
        try:
            conn.execute(f"ALTER TABLE leads ADD COLUMN {col} TEXT DEFAULT ''")
            conn.commit()
        except Exception:
            pass

    # Migration: add proxy_contracts column to watchlist if missing
    try:
        conn.execute("ALTER TABLE watchlist ADD COLUMN proxy_contracts TEXT DEFAULT '{}'")
        conn.commit()
    except Exception:
        pass


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
                          funding, tech, audit_status, summary, pitch_services, score_breakdown,
                          scored_by, lead_group, listed_at, website_url, twitter_url, github_url, defillama_url)
        VALUES (?, ?, ?, ?, ?, ?, 'Discovered', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        lead.get("pitch_services") if isinstance(lead.get("pitch_services"), str) else ", ".join(lead.get("pitch_services", [])),
        lead.get("score_breakdown") if isinstance(lead.get("score_breakdown"), str) else json.dumps(lead.get("score_breakdown", {}), ensure_ascii=False),
        lead.get("scored_by", "heuristic"),
        lead.get("lead_group", "A"),
        lead.get("listed_at", ""),
        lead.get("website_url", ""),
        lead.get("twitter_url", ""),
        lead.get("github_url", ""),
        lead.get("defillama_url", ""),
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
    allowed = ["stage", "priority", "contact_notes", "follow_up_date", "category",
               "score", "audit_status", "score_breakdown", "scored_by", "summary",
               "pitch_services"]
    fields = []
    params = []
    for key in allowed:
        if key in updates:
            fields.append(f"{key} = ?")
            params.append(updates[key])

    if not fields:
        return False

    fields.append("updated_at = datetime('now','localtime')")
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
                              category, last_audit_date, auditor, client_type,
                              proxy_contracts, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        project.get("name", ""),
        project.get("github_repo", ""),
        project.get("snapshot_space", ""),
        project.get("x_account", ""),
        project.get("category", ""),
        project.get("last_audit_date", ""),
        project.get("auditor", ""),
        project.get("client_type", ""),
        project.get("proxy_contracts", "{}"),
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
               "category", "last_audit_date", "auditor", "client_type",
               "proxy_contracts", "notes"]
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
    cursor = conn.execute(
        "INSERT INTO scan_logs (scan_type, started_at) VALUES (?, datetime('now','localtime'))",
        (scan_type,))
    conn.commit()
    return cursor.lastrowid


def complete_scan_log(log_id: int, leads_found: int = 0, hot: int = 0, warm: int = 0, details: str = ""):
    conn = get_conn()
    conn.execute("""
        UPDATE scan_logs SET status='completed', leads_found=?, hot_count=?,
               warm_count=?, details=?, completed_at=datetime('now','localtime')
        WHERE id = ?
    """, (leads_found, hot, warm, details, log_id))
    conn.commit()


def fail_scan_log(log_id: int, error: str):
    conn = get_conn()
    conn.execute("""
        UPDATE scan_logs SET status='failed', details=?, completed_at=datetime('now','localtime')
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


def reset_database():
    """Wipe all leads, scan_logs, and incidents. Keep watchlist intact."""
    conn = get_conn()
    conn.execute("DELETE FROM leads")
    conn.execute("DELETE FROM scan_logs")
    conn.execute("DELETE FROM incidents")
    conn.commit()
    print("[DB] 🗑️  Database reset — leads, scan_logs, incidents cleared")
    return {"ok": True, "message": "Database reset. Leads, scan_logs, incidents cleared."}
