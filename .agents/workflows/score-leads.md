---
description: Score leads with Antigravity AI — includes web search for audit verification
---

# /score-leads Workflow

This workflow scores unscored leads using Antigravity AI analysis with web-based audit verification.
Run daily or on-demand after a DeFiLlama scan (`/api/run-scan/leads`).

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

### 2. Web Search Audit Status (for EACH unscored lead)
For every lead from step 1, use the `search_web` tool to check:
```
Query: "{project name}" smart contract audit report security review
```

Classify the result:
- ✅ **Audited** → note auditor name, date, link to report
- ⚠️ **Partially audited** → older audit, or only V1 audited
- ❌ **No audit found** → high priority target

Also search for:
```
Query: "{project name}" fundraise seed round team
```
To gather funding/team context for scoring.

### 3. Score Each Lead
Using all gathered context (DeFiLlama data + web search results), assign scores using the Verichains rubric:

| Dimension | Max Points | What to evaluate |
|-----------|-----------|-----------------|
| Audit Need | 25 | Is there a public audit? How old? How complex? |
| Funding & Budget | 15 | TVL, known fundraise, team backing |
| Category Fit | 15 | DeFi/bridge/ZK = high, generic = low |
| Growth & Timing | 10 | New launch? V2 upgrade? Rapid TVL growth? |
| Verichains Moat | 5 | ZK, cryptography, novel primitives? |
| Base Score | 30 | Overall impression |

Priority mapping:
- ≥75 → HOT
- ≥55 → WARM
- ≥40 → MONITOR
- <40 → LOW

Lead Group:
- A = Net-New (never been Verichains client)
- B = Upgrade (existing project, re-audit opportunity)
- C = Incident Response
- D = Compliance

### 4. Push Scores to API
```
curl -s -X POST https://leadhunter-nine.vercel.app/api/leads/bulk-score \
  -H "Content-Type: application/json" \
  -d '{"scores": [
    {"id": <ID>, "score": <N>, "priority": "<P>", "lead_group": "<G>",
     "summary": "<AI summary with audit context>",
     "audit_status": "<status with link to report>",
     "score_breakdown": {<dimension breakdown>},
     "pitch_services": ["<relevant services>"],
     "funding": "<funding info>", "tech": "<tech stack>",
     "scored_by": "ai:antigravity"}
  ]}'
```

### 5. Verify
// turbo
```
curl -s https://leadhunter-nine.vercel.app/api/leads/unscored | python3 -c "
import sys, json; print(f'Remaining unscored: {json.load(sys.stdin)[\"count\"]}')
"
```

## Key Rules
- **ALWAYS web search before scoring** — DeFiLlama alone is insufficient
- Include audit report links in `audit_status` field when found
- Mark tokenized stocks/non-protocols as LOW with clear explanation
- For already-audited projects: reduce Audit Need points, note auditor + date
