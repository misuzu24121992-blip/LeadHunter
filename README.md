# 🔍 Verichains LeadHunter

**Signal-based Lead Generation** cho Blockchain Security Services.  
Tool cá nhân — Python scripts + OpenAI + Airtable + Telegram Bot.

## Kiến Trúc

```
Python Scripts → OpenAI gpt-4o-mini → Airtable (Kanban) → Telegram (Alerts)
```

| Script | Chức năng | Tần suất |
|--------|----------|---------|
| `lead_hunter.py` | Tìm dự án mới (DeFiLlama + RootData) | Mỗi 6h |
| `upgrade_watcher.py` | Monitor GitHub + Governance upgrades | Mỗi 1h |
| `incident_radar.py` | Phát hiện hacks (Rekt News) | Mỗi 30 phút |
| `run_all.py` | Chạy tất cả scripts | Cron job |

## Setup Nhanh (5 phút)

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Tạo file `.env`
```bash
cp .env.example .env
```
Sau đó điền API keys vào `.env`:

| Key | Cách lấy | Bắt buộc? |
|-----|---------|----------|
| `OPENAI_API_KEY` | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) | ✅ Có |
| `TELEGRAM_BOT_TOKEN` | Chat với [@BotFather](https://t.me/BotFather) trên Telegram | ✅ Có |
| `TELEGRAM_CHAT_ID` | Gửi tin nhắn cho bot → mở `https://api.telegram.org/bot<TOKEN>/getUpdates` | ✅ Có |
| `AIRTABLE_API_KEY` | [airtable.com/create/tokens](https://airtable.com/create/tokens) | ✅ Có |
| `AIRTABLE_BASE_ID` | Mở Airtable base → URL chứa `app...` | ✅ Có |
| `GITHUB_TOKEN` | [github.com/settings/tokens](https://github.com/settings/tokens) | ⚡ Nên có |
| `ROOTDATA_API_KEY` | [rootdata.com](https://www.rootdata.com/) | 📌 Optional |

### 3. Setup Airtable

Tạo 2 tables trong Airtable base:

**Table 1: Pipeline Tracker**
| Field | Type |
|-------|------|
| Project Name | Single line text |
| Category | Single select: DeFi, GameFi, RWA, ZK, L1-L2, Other |
| Score | Number |
| Priority | Single select: 🔴 HOT, 🟡 WARM, 🟢 MONITOR, ⚪ LOW |
| Source | Single select: RootData, DeFiLlama, Hackathon, GitHub, Incident |
| Trigger | Long text |
| Stage | Single select: Discovered, Researching, Outreach, Proposal, Won, Lost |
| Funding | Single line text |
| AI Summary | Long text |
| Contact Notes | Long text |
| Follow-up Date | Date |

**Table 2: Watchlist** (cho upgrade_watcher)
| Field | Type |
|-------|------|
| Project Name | Single line text |
| GitHub Repo | URL |
| Snapshot Space | Single line text |
| X Account | Single line text |
| Category | Single select |
| Last Audit Date | Date |
| Auditor | Single line text |
| Client Type | Single select: Khách cũ, Mid-cap, ZK Target, L2 |
| Notes | Long text |

### 4. Setup Watchlist

**Option A (Airtable):** Thêm dự án trực tiếp vào Watchlist table.

**Option B (Local):** Copy và chỉnh sửa file JSON:
```bash
cp watchlist.example.json watchlist.json
```

### 5. Chạy thử
```bash
# Test Telegram
python telegram_bot.py

# Chạy lead hunter
python lead_hunter.py

# Chạy upgrade watcher
python upgrade_watcher.py

# Chạy incident radar
python incident_radar.py

# Chạy tất cả
python run_all.py
```

### 6. Setup Cron (Tự động)

```bash
crontab -e
```

Thêm:
```cron
# Lead Hunter — mỗi 6 giờ (7:30, 13:30, 19:30, 1:30)
30 7,13,19,1 * * * cd /path/to/velvet-exoplanet && /usr/bin/python3 lead_hunter.py >> /tmp/leadhunter.log 2>&1

# Upgrade Watcher — mỗi giờ
0 * * * * cd /path/to/velvet-exoplanet && /usr/bin/python3 upgrade_watcher.py >> /tmp/upgrade_watcher.log 2>&1

# Incident Radar — mỗi 30 phút
*/30 * * * * cd /path/to/velvet-exoplanet && /usr/bin/python3 incident_radar.py >> /tmp/incident_radar.log 2>&1
```

## Chi phí ước tính: ~$5-20/tháng

| Item | Chi phí | Ghi chú |
|------|---------|---------|
| OpenAI (gpt-4o-mini) | ~$5-15 | ~500-1000 items/ngày |
| Airtable | $0 | Free tier |
| Telegram Bot | $0 | Free |
| VPS (nếu cần) | ~$5 | Optional |

## File Structure

```
├── config.py              # API keys + constants
├── telegram_bot.py        # Telegram alert helper
├── ai_scorer.py           # OpenAI scoring + noise filter
├── airtable_client.py     # Airtable read/write
├── lead_hunter.py         # Script 1: New project discovery
├── upgrade_watcher.py     # Script 2: GitHub + Governance monitor
├── incident_radar.py      # Script 3: Hack/incident monitor
├── run_all.py             # Run all scripts (for cron)
├── watchlist.example.json # Example watchlist format
├── requirements.txt       # Python dependencies
├── .env.example           # Environment variables template
└── .gitignore
```
