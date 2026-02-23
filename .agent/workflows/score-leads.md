---
description: Score unscored leads using Antigravity AI analysis
---

## Score Leads Workflow

Use this workflow when there are heuristic-scored leads that need deeper AI analysis.

### Steps

1. **Fetch unscored leads** from the Vercel API:
// turbo
```
curl -s https://leadhunter-nine.vercel.app/api/leads/unscored | python3 -m json.tool
```

2. **Analyze each lead** considering Verichains' services:
   - **Audit Need Score** (0-25): Does their tech stack (L1, DEX, Lending, Bridge) need a smart contract audit?
   - **Funding/Backer Quality** (0-15): Can they afford Verichains? Look at TVL, funding rounds
   - **Category Fit** (0-15): Lending, DEX, Bridge, Cross-chain = highest audit need
   - **Growth & Timing** (0-10): Is TVL growing? New launch = audit urgency
   - **Description Signals** (0-5): Keywords like "smart contract", "DeFi", "bridge", "cross-chain"
   - **Base Score** (30): Starting baseline for all protocols
   
   Priority thresholds: HOT ≥ 75, WARM ≥ 55, MONITOR ≥ 40

3. **For each lead**, generate:
   - `score` (0-100)
   - `priority` ("HOT", "WARM", "MONITOR", or "LOW")
   - `summary` — 2-3 sentence analysis of the project and why it's relevant to Verichains
   - `score_breakdown` — JSON dict with category scores like `{"Audit Need": {"points": 20, "max": 25, "reason": "..."}, ...}`
   - `audit_status` — Assessment of their current audit situation
   - `pitch_services` — List of Verichains services to pitch (e.g., ["Smart Contract Audit", "Penetration Testing"])
   - `funding` — Funding info summary
   - `tech` — Tech stack / chains

4. **Push results** via API:
```
curl -X POST https://leadhunter-nine.vercel.app/api/leads/bulk-score \
  -H "Content-Type: application/json" \
  -d '{"scores": [{"id": 1, "score": 85, "priority": "HOT", ...}]}'
```

5. **Verify** by checking the dashboard — leads should show "🤖 AI:Antigravity" badge
