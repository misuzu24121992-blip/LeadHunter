---
description: Score leads with Antigravity AI — includes 5-step audit verification pipeline
---

# /score-leads Workflow

Score unscored leads using Antigravity AI with comprehensive audit verification.
Run daily or on-demand after a DeFiLlama scan.

## Prerequisites
- Leads must exist in the pipeline (run a scan first if empty)
- Vercel deployment must be live at `leadhunter-nine.vercel.app`

## Steps

### 1. Fetch Unscored Leads
// turbo
```
curl -s https://leadhunter-nine.vercel.app/api/leads/unscored | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f'Unscored: {d[\"count\"]}')
for l in d['leads']:
    print(f'  ID {l[\"id\"]}: {l[\"name\"]} ({l[\"category\"]}) TVL={l.get(\"funding\",\"?\")}')
"
```

### 2. Audit Verification Pipeline (for EACH unscored lead)

Run these 5 checks **in order** for every lead. Stop early if a definitive answer is found.

#### Step 2a — GitHub Audit Folder Check
If the lead has a `github_url`, use `read_url_content` to check:
```
{github_url}/tree/main/audits
{github_url}/tree/main/audit
{github_url}/tree/main/security
```
Look for PDF audit reports, auditor names, and dates.

**Example**: atomiq exchange → `github.com/atomiqlabs/atomiq-readme/tree/main/audits` → ✅ Found

#### Step 2b — Web Search (Smart Contract Audit)
Use `search_web` tool with these queries:
```
"{project name}" smart contract audit report
"{project name}" security audit blockchain
```
Look for: auditor name, report date, report link, severity findings.

#### Step 2c — Audit Database Check
Use `search_web` with site-specific queries:
```
site:skynet.certik.com "{project name}"
site:solodit.xyz "{project name}"
site:defisafety.com "{project name}"
site:app.sherlock.xyz "{project name}"
```

#### Step 2d — Project Docs Crawl
If the lead has a `website_url`, use `read_url_content` to check:
```
{website_url}/security
{website_url}/audits
{website_url}/docs/security
```
Many protocols list their audits on a dedicated security page.

**Example**: Cooler Loans → `docs.olympusdao.finance/main/security/audits` → ✅ 3 audits listed

#### Step 2e — Classify Audit Status
Based on all gathered data, classify:
- ✅ **Audited** → `"✅ Audited by {auditor} ({date}) — {link}"` — reduce Audit Need score
- ⚠️ **Stale audit** → `"⚠️ Last audit: {date} by {auditor}. Re-audit recommended."` — moderate score
- ❌ **No audit found** → `"❌ No known public audit"` — high Audit Need score
- 🚫 **Not applicable** → `"N/A — not a smart contract protocol"` (e.g. EXOD = tokenized stock)

### 3. Funding & Team Research
Use `search_web` for each lead:
```
"{project name}" fundraise seed round investors
"{project name}" team founders blockchain
```
Note: funding info affects budget score (can they afford an audit?).

### 4. Score Each Lead
Using DeFiLlama data + audit verification + funding research, assign scores:

| Dimension | Max | Guide |
|-----------|-----|-------|
| Audit Need | 25 | ❌ No audit = 20-25, ⚠️ Stale = 10-15, ✅ Recent = 2-8 |
| Funding & Budget | 15 | $50M+ TVL = 12-15, $1M+ = 8-11, <$100K = 1-4 |
| Category Fit | 15 | Bridge/lending/DEX = 12-15, gaming/NFT = 5-8 |
| Growth & Timing | 10 | V2 just launched = 8-10, mature = 2-4 |
| Verichains Moat | 5 | ZK/crypto = 4-5, standard = 1-2 |
| Base Score | 30 | Overall impression of opportunity quality |

Priority: ≥75 HOT, ≥55 WARM, ≥40 MONITOR, <40 LOW

Lead Group: A=Net-New, B=Upgrade, C=Incident, D=Compliance

### 5. Push Scores to API
```
curl -s -X POST https://leadhunter-nine.vercel.app/api/leads/bulk-score \
  -H "Content-Type: application/json" \
  -d '{"scores": [
    {"id": <ID>, "score": <N>, "priority": "<P>", "lead_group": "<G>",
     "summary": "<include audit context from step 2>",
     "audit_status": "<classified status with link>",
     "score_breakdown": {<6 dimensions>},
     "pitch_services": ["<relevant>"],
     "funding": "<info>", "tech": "<stack>",
     "scored_by": "ai:antigravity"}
  ]}'
```

### 6. Verify
// turbo
```
curl -s https://leadhunter-nine.vercel.app/api/leads/unscored | python3 -c "
import sys, json; print(f'Remaining unscored: {json.load(sys.stdin)[\"count\"]}')
"
```

### 7. Notify User for Manual Confirmation
After scoring, present a summary table to the user for review.
User may override scores based on their domain knowledge (Step 5 of the audit pipeline).
This is critical — AI may miss context that only a human expert knows.

## Key Rules
- **NEVER skip audit verification** — DeFiLlama alone is insufficient
- **Include audit report links** in `audit_status` when found
- **Flag non-protocols** (tokenized stocks, wrapped tokens) as LOW
- **Already-audited = lower score** unless stale (>1 year) or major upgrade
- **Cross-chain bridges and novel primitives** deserve higher Verichains Moat scores
