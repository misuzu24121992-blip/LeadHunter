"""
Verichains LeadHunter — Configuration
Loads environment variables and defines constants.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ========== API Keys ==========
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY", "")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID", "")
AIRTABLE_PIPELINE_TABLE = os.getenv("AIRTABLE_PIPELINE_TABLE", "Pipeline Tracker")
AIRTABLE_WATCHLIST_TABLE = os.getenv("AIRTABLE_WATCHLIST_TABLE", "Watchlist")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
ROOTDATA_API_KEY = os.getenv("ROOTDATA_API_KEY", "")

# ========== DeFiLlama ==========
DEFILLAMA_API_BASE = "https://api.llama.fi"
DEFILLAMA_NEW_PROTOCOL_DAYS = 7  # Look back N days for new protocols

# ========== RootData ==========
ROOTDATA_API_BASE = "https://api.rootdata.com/open/ser_inv"

# ========== GitHub ==========
GITHUB_API_BASE = "https://api.github.com"
GITHUB_WATCH_DIRS = [
    "contracts", "src", "circuits", "pallets", "crates",
    "programs", "sources", "modules",
]
GITHUB_IGNORE_DIRS = [
    "docs", "test", "tests", "ci", ".github", "scripts",
    "deploy", "deployments",
]
GITHUB_UPGRADE_KEYWORDS = [
    "v2", "v3", "v4", "upgrade", "migration", "audit-prep",
    "breaking", "security", "mainnet", "launch",
]

# ========== Snapshot Governance ==========
SNAPSHOT_GRAPHQL_URL = "https://hub.snapshot.org/graphql"
SNAPSHOT_UPGRADE_KEYWORDS = [
    "upgrade", "v2", "v3", "migration", "audit",
    "budget", "security", "new version",
]

# ========== Incident Monitoring ==========
REKT_NEWS_RSS = "https://rekt.news/rss.xml"

# ========== Scoring ==========
SCORE_HOT_THRESHOLD = 80
SCORE_WARM_THRESHOLD = 60
SCORE_MONITOR_THRESHOLD = 40

# ========== Model ==========
# AI Provider: auto-detect. Priority: Gemini > Anthropic > OpenAI
if GEMINI_API_KEY:
    AI_PROVIDER = "gemini"
elif ANTHROPIC_API_KEY:
    AI_PROVIDER = "anthropic"
elif OPENAI_API_KEY:
    AI_PROVIDER = "openai"
else:
    AI_PROVIDER = "none"

OPENAI_MODEL = "gpt-4o-mini"
ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
GEMINI_MODEL = "gemini-2.0-flash"
AI_MAX_TOKENS = 2000
