#!/usr/bin/env python3
"""Fix Tramplin and Paimon audit status on both localhost and Vercel."""

import json, requests

fixes = {
    "tramplin.io": {
        "audit_status": "✅ Audited by MixBytes (2025) — report on GitHub",
        "score": 42,  # Reduce: audit already done, less opportunity
        "priority": "MONITOR",
        "summary": "Tramplin.io Solana native staking pool ($12M TVL). Audited by MixBytes (late 2025) — transparent architecture, reward distribution verified on-chain.",
        "score_breakdown": {
            "Audit Need": {"points": 5, "max": 25, "note": "Already audited by MixBytes"},
            "Funding & Budget": {"points": 9, "max": 15},
            "Category Fit": {"points": 8, "max": 15},
            "Growth & Timing": {"points": 4, "max": 10},
            "Verichains Moat": {"points": 2, "max": 5},
            "Base Score": {"points": 14, "max": 30}
        },
        "pitch_services": ["Penetration Testing", "Re-audit"],
    },
    "Paimon": {
        "audit_status": "✅ Audited by CertiK — Skynet security score, team verified, bug bounty active",
        "score": 45,  # Reduce: already audited by CertiK
        "priority": "MONITOR",
        "summary": "Paimon Finance RWA tokenization on BNB Chain ($753K TVL). BNB MVB S8 + YZi Labs. CertiK audited with Skynet score, team verification, and bug bounty.",
        "score_breakdown": {
            "Audit Need": {"points": 5, "max": 25, "note": "CertiK audited"},
            "Funding & Budget": {"points": 6, "max": 15},
            "Category Fit": {"points": 13, "max": 15},
            "Growth & Timing": {"points": 5, "max": 10},
            "Verichains Moat": {"points": 2, "max": 5},
            "Base Score": {"points": 14, "max": 30}
        },
        "pitch_services": ["Smart Contract Re-audit", "Penetration Testing"],
    }
}


def push_fixes(base_url, label):
    # Get all leads to find IDs by name
    resp = requests.get(f"{base_url}/api/leads", timeout=15)
    leads = resp.json()
    name_to_id = {l["name"]: l["id"] for l in leads}
    
    scores = []
    for name, fix in fixes.items():
        if name in name_to_id:
            entry = {"id": name_to_id[name], "scored_by": "ai:antigravity", **fix}
            scores.append(entry)
            print(f"  [{label}] {name} (ID {name_to_id[name]}): {fix['audit_status'][:60]}")
        else:
            print(f"  [{label}] ⚠️  {name} not found!")
    
    resp = requests.post(f"{base_url}/api/leads/bulk-score", json={"scores": scores}, timeout=15)
    print(f"  [{label}] → {resp.status_code}: {resp.json()}")


print("=== Fixing Tramplin + Paimon audit status ===\n")

print("Localhost:")
push_fixes("http://localhost:8000", "local")

print("\nVercel:")
push_fixes("https://leadhunter-nine.vercel.app", "vercel")
