#!/usr/bin/env python3
"""Push Antigravity AI scores to Vercel LeadHunter API — maps by name."""

import json, requests

API = "https://leadhunter-nine.vercel.app/api/leads/bulk-score"

# First fetch all unscored leads to get name→id mapping
resp = requests.get("https://leadhunter-nine.vercel.app/api/leads/unscored", timeout=15)
unscored = resp.json()["leads"]
name_to_id = {l["name"]: l["id"] for l in unscored}
print(f"Found {len(name_to_id)} unscored leads on Vercel")

# Score data keyed by name
score_data = {
    "Cooler Loans": {"score": 35, "priority": "LOW", "lead_group": "A",
     "summary": "Cooler Loans is Olympus DAO's protocol-native lending system. Multiple audits: Sherlock (Aug 2023), Nethermind Cooler V2, V2 Migrator reviews. TVL $196M is strong but already well-audited — low opportunity.",
     "audit_status": "✅ Audited by Sherlock (2023-08), Nethermind (Cooler V2) — docs.olympusdao.finance/security/audits",
     "score_breakdown": {"Audit Need": {"points": 3, "max": 25}, "Funding & Budget": {"points": 12, "max": 15}, "Category Fit": {"points": 10, "max": 15}, "Growth & Timing": {"points": 3, "max": 10}, "Verichains Moat": {"points": 2, "max": 5}, "Base Score": {"points": 5, "max": 30}},
     "pitch_services": ["Smart Contract Audit"], "funding": "TVL: $196M", "tech": "Solidity, EVM"},

    "Exod": {"score": 20, "priority": "LOW", "lead_group": "D",
     "summary": "Exod is a tokenized stock platform (Exodus Movement). SEC-compliant shares on Algorand/Solana. Not a smart contract protocol.",
     "audit_status": "🚫 N/A — tokenized stock, not a smart contract protocol",
     "score_breakdown": {"Audit Need": {"points": 1, "max": 25}, "Funding & Budget": {"points": 10, "max": 15}, "Category Fit": {"points": 2, "max": 15}, "Growth & Timing": {"points": 2, "max": 10}, "Verichains Moat": {"points": 1, "max": 5}, "Base Score": {"points": 4, "max": 30}},
     "pitch_services": [], "funding": "TVL: $291M — NASDAQ", "tech": "Algorand, Solana"},

    "tramplin.io": {"score": 55, "priority": "WARM", "lead_group": "A",
     "summary": "Tramplin.io Solana native staking pool ($12M TVL). No SC custody. No audit found.",
     "audit_status": "❌ No known public audit — Solana native staking",
     "score_breakdown": {"Audit Need": {"points": 12, "max": 25}, "Funding & Budget": {"points": 9, "max": 15}, "Category Fit": {"points": 8, "max": 15}, "Growth & Timing": {"points": 6, "max": 10}, "Verichains Moat": {"points": 2, "max": 5}, "Base Score": {"points": 18, "max": 30}},
     "pitch_services": ["Penetration Testing", "Infrastructure Security Review"], "funding": "TVL: $12.3M", "tech": "Solana"},

    "Royco V2": {"score": 30, "priority": "LOW", "lead_group": "A",
     "summary": "Royco V2 yield marketplace ($7.7M TVL). 6+ auditors: Spearbit, Cantina, OtterSec, Zellic, Nethermind, yAudit.",
     "audit_status": "✅ Extensively audited by Spearbit, Cantina, OtterSec, Zellic, Nethermind, yAudit",
     "score_breakdown": {"Audit Need": {"points": 2, "max": 25}, "Funding & Budget": {"points": 8, "max": 15}, "Category Fit": {"points": 8, "max": 15}, "Growth & Timing": {"points": 4, "max": 10}, "Verichains Moat": {"points": 2, "max": 5}, "Base Score": {"points": 6, "max": 30}},
     "pitch_services": ["Smart Contract Audit"], "funding": "TVL: $7.7M", "tech": "Solidity, EVM"},

    "EGAS swap": {"score": 62, "priority": "WARM", "lead_group": "A",
     "summary": "EGAS Swap part of ENI (Eniac Network), modular L1. CertiK audit in progress. L1 + DEX = strong Verichains fit.",
     "audit_status": "⚠️ CertiK audit in progress for ENI ecosystem",
     "score_breakdown": {"Audit Need": {"points": 15, "max": 25}, "Funding & Budget": {"points": 8, "max": 15}, "Category Fit": {"points": 12, "max": 15}, "Growth & Timing": {"points": 7, "max": 10}, "Verichains Moat": {"points": 4, "max": 5}, "Base Score": {"points": 16, "max": 30}},
     "pitch_services": ["Blockchain L1 Audit", "Smart Contract Audit"], "funding": "TVL: $6.4M", "tech": "Modular L1 (ENI)"},

    "TokenLabs": {"score": 40, "priority": "MONITOR", "lead_group": "A",
     "summary": "TokenLabs IOTA liquid staking ($625K TVL). Audited by AuditOne, SolidProof, MoveBit.",
     "audit_status": "✅ Audited by AuditOne, SolidProof, MoveBit",
     "score_breakdown": {"Audit Need": {"points": 4, "max": 25}, "Funding & Budget": {"points": 5, "max": 15}, "Category Fit": {"points": 10, "max": 15}, "Growth & Timing": {"points": 5, "max": 10}, "Verichains Moat": {"points": 2, "max": 5}, "Base Score": {"points": 14, "max": 30}},
     "pitch_services": ["Smart Contract Audit"], "funding": "TVL: $625K", "tech": "IOTA"},

    "atomiq exchange": {"score": 42, "priority": "MONITOR", "lead_group": "A",
     "summary": "atomiq exchange cross-chain atomic swap bridge ($243K TVL). Audited by Ackee Blockchain (Dec 2023).",
     "audit_status": "✅ Audited by Ackee Blockchain (Dec 2023, re-audit Jan 2024)",
     "score_breakdown": {"Audit Need": {"points": 8, "max": 25}, "Funding & Budget": {"points": 4, "max": 15}, "Category Fit": {"points": 14, "max": 15}, "Growth & Timing": {"points": 5, "max": 10}, "Verichains Moat": {"points": 3, "max": 5}, "Base Score": {"points": 8, "max": 30}},
     "pitch_services": ["Smart Contract Audit", "Cryptography Audit"], "funding": "TVL: $243K", "tech": "Solana, Bitcoin"},

    "Spreads Finance": {"score": 60, "priority": "WARM", "lead_group": "A",
     "summary": "Spreads Finance yield protocol ($193K TVL). No audit found. Handles user funds without audit.",
     "audit_status": "❌ No known public audit",
     "score_breakdown": {"Audit Need": {"points": 22, "max": 25}, "Funding & Budget": {"points": 3, "max": 15}, "Category Fit": {"points": 10, "max": 15}, "Growth & Timing": {"points": 7, "max": 10}, "Verichains Moat": {"points": 2, "max": 5}, "Base Score": {"points": 16, "max": 30}},
     "pitch_services": ["Smart Contract Audit"], "funding": "TVL: $193K", "tech": "EVM"},

    "Zentra Finance": {"score": 65, "priority": "WARM", "lead_group": "A",
     "summary": "Zentra Finance lending on Citrea (Bitcoin ZK rollup), Aave fork. Under audit. ZK = Verichains specialty.",
     "audit_status": "⚠️ Under audit (per zentra.finance) — no completed report yet",
     "score_breakdown": {"Audit Need": {"points": 18, "max": 25}, "Funding & Budget": {"points": 3, "max": 15}, "Category Fit": {"points": 13, "max": 15}, "Growth & Timing": {"points": 8, "max": 10}, "Verichains Moat": {"points": 4, "max": 5}, "Base Score": {"points": 19, "max": 30}},
     "pitch_services": ["Smart Contract Audit", "Cryptography Audit (ZK)"], "funding": "TVL: $176K", "tech": "Citrea (Bitcoin ZK rollup)"},

    "Alphix": {"score": 55, "priority": "WARM", "lead_group": "A",
     "summary": "Alphix DEX ($124K TVL). No audit — Hook v2 audit planned Q2 2026. Good timing to pitch.",
     "audit_status": "❌ No audit — Hook v2 audit planned for Q2 2026",
     "score_breakdown": {"Audit Need": {"points": 22, "max": 25}, "Funding & Budget": {"points": 3, "max": 15}, "Category Fit": {"points": 10, "max": 15}, "Growth & Timing": {"points": 8, "max": 10}, "Verichains Moat": {"points": 2, "max": 5}, "Base Score": {"points": 10, "max": 30}},
     "pitch_services": ["Smart Contract Audit"], "funding": "TVL: $124K", "tech": "EVM"},

    "Paimon": {"score": 62, "priority": "WARM", "lead_group": "A",
     "summary": "Paimon Finance RWA tokenization on BNB Chain ($753K TVL). BNB MVB S8 + YZi Labs. No audit.",
     "audit_status": "❌ No known public audit — partner MyStonks has CertiK audit",
     "score_breakdown": {"Audit Need": {"points": 22, "max": 25}, "Funding & Budget": {"points": 6, "max": 15}, "Category Fit": {"points": 13, "max": 15}, "Growth & Timing": {"points": 7, "max": 10}, "Verichains Moat": {"points": 2, "max": 5}, "Base Score": {"points": 12, "max": 30}},
     "pitch_services": ["Smart Contract Audit", "Penetration Testing"], "funding": "TVL: $753K, BNB MVB S8", "tech": "BNB Chain, RWA"},

    "Alpaca Dex": {"score": 40, "priority": "MONITOR", "lead_group": "A",
     "summary": "Alpaca Dex on Keeta ($138K TVL). Off-chain liquidity — SC not deployed yet.",
     "audit_status": "❌ No SC deployed — off-chain management",
     "score_breakdown": {"Audit Need": {"points": 15, "max": 25}, "Funding & Budget": {"points": 3, "max": 15}, "Category Fit": {"points": 8, "max": 15}, "Growth & Timing": {"points": 5, "max": 10}, "Verichains Moat": {"points": 2, "max": 5}, "Base Score": {"points": 7, "max": 30}},
     "pitch_services": ["Smart Contract Audit"], "funding": "TVL: $138K", "tech": "Keeta"},

    "Stobox": {"score": 38, "priority": "LOW", "lead_group": "D",
     "summary": "Stobox tokenization services ($23M TVL). CertiK audited.",
     "audit_status": "✅ CertiK audit completed for Stobox Exchange",
     "score_breakdown": {"Audit Need": {"points": 4, "max": 25}, "Funding & Budget": {"points": 10, "max": 15}, "Category Fit": {"points": 5, "max": 15}, "Growth & Timing": {"points": 3, "max": 10}, "Verichains Moat": {"points": 1, "max": 5}, "Base Score": {"points": 15, "max": 30}},
     "pitch_services": ["Smart Contract Audit"], "funding": "TVL: $23M", "tech": "EVM"},

    "Murphy": {"score": 42, "priority": "MONITOR", "lead_group": "A",
     "summary": "Murphy DEX ($89K TVL). No info available.",
     "audit_status": "❌ No known public audit",
     "score_breakdown": {"Audit Need": {"points": 18, "max": 25}, "Funding & Budget": {"points": 2, "max": 15}, "Category Fit": {"points": 8, "max": 15}, "Growth & Timing": {"points": 4, "max": 10}, "Verichains Moat": {"points": 1, "max": 5}, "Base Score": {"points": 9, "max": 30}},
     "pitch_services": ["Smart Contract Audit"], "funding": "TVL: $89K", "tech": "Unknown"},

    "Stone Vault": {"score": 40, "priority": "MONITOR", "lead_group": "A",
     "summary": "Stone Vault (stva.io) yield aggregator ($52K TVL). StakeStone ecosystem audited by Quantstamp.",
     "audit_status": "⚠️ StakeStone ecosystem audited by Quantstamp + Veridise",
     "score_breakdown": {"Audit Need": {"points": 12, "max": 25}, "Funding & Budget": {"points": 2, "max": 15}, "Category Fit": {"points": 8, "max": 15}, "Growth & Timing": {"points": 5, "max": 10}, "Verichains Moat": {"points": 2, "max": 5}, "Base Score": {"points": 11, "max": 30}},
     "pitch_services": ["Smart Contract Audit"], "funding": "TVL: $52K", "tech": "EVM"},

    "Normal": {"score": 50, "priority": "MONITOR", "lead_group": "A",
     "summary": "Normal Finance derivatives/index on Stellar ($33K TVL). Claims audited but no report found.",
     "audit_status": "⚠️ Claims audited per normalfinance.io — no public report",
     "score_breakdown": {"Audit Need": {"points": 15, "max": 25}, "Funding & Budget": {"points": 2, "max": 15}, "Category Fit": {"points": 10, "max": 15}, "Growth & Timing": {"points": 5, "max": 10}, "Verichains Moat": {"points": 2, "max": 5}, "Base Score": {"points": 16, "max": 30}},
     "pitch_services": ["Smart Contract Audit"], "funding": "TVL: $33K", "tech": "Stellar"},

    "DeltaDeFi": {"score": 52, "priority": "MONITOR", "lead_group": "A",
     "summary": "DeltaDeFi DEX on Cardano ($80K TVL). BlockSec audit found 10 High + 9 Medium issues.",
     "audit_status": "⚠️ DeltaTrade audited by BlockSec — 10 High + 9 Medium risk issues",
     "score_breakdown": {"Audit Need": {"points": 18, "max": 25}, "Funding & Budget": {"points": 2, "max": 15}, "Category Fit": {"points": 8, "max": 15}, "Growth & Timing": {"points": 5, "max": 10}, "Verichains Moat": {"points": 3, "max": 5}, "Base Score": {"points": 16, "max": 30}},
     "pitch_services": ["Smart Contract Audit"], "funding": "TVL: $80K", "tech": "Cardano"},

    "ETMCv2": {"score": 25, "priority": "LOW", "lead_group": "A",
     "summary": "ETMCv2 DEX ($1.7K TVL). Not viable.", "audit_status": "❌ No known public audit",
     "score_breakdown": {"Audit Need": {"points": 10, "max": 25}, "Funding & Budget": {"points": 1, "max": 15}, "Category Fit": {"points": 5, "max": 15}, "Growth & Timing": {"points": 2, "max": 10}, "Verichains Moat": {"points": 1, "max": 5}, "Base Score": {"points": 6, "max": 30}},
     "pitch_services": [], "funding": "TVL: $1.7K", "tech": "ETCMC"},

    "Nexion Vaults": {"score": 25, "priority": "LOW", "lead_group": "A",
     "summary": "Nexion Vaults ($1K TVL). Not viable.", "audit_status": "❌ No known public audit",
     "score_breakdown": {"Audit Need": {"points": 10, "max": 25}, "Funding & Budget": {"points": 1, "max": 15}, "Category Fit": {"points": 5, "max": 15}, "Growth & Timing": {"points": 2, "max": 10}, "Verichains Moat": {"points": 1, "max": 5}, "Base Score": {"points": 6, "max": 30}},
     "pitch_services": [], "funding": "TVL: $1K", "tech": "Unknown"},

    "OK-BITOK Vault": {"score": 22, "priority": "LOW", "lead_group": "A",
     "summary": "OK-BITOK Vault ($611 TVL). Not viable.", "audit_status": "❌ No known public audit",
     "score_breakdown": {"Audit Need": {"points": 8, "max": 25}, "Funding & Budget": {"points": 1, "max": 15}, "Category Fit": {"points": 4, "max": 15}, "Growth & Timing": {"points": 2, "max": 10}, "Verichains Moat": {"points": 1, "max": 5}, "Base Score": {"points": 6, "max": 30}},
     "pitch_services": [], "funding": "TVL: $611", "tech": "Unknown"},

    "Floe Labs": {"score": 50, "priority": "MONITOR", "lead_group": "A",
     "summary": "Floe Labs — first Credit DEX, intent-based lending ($278 TVL). Audited + Immunefi bounty.",
     "audit_status": "✅ Audited — report via Immunefi bug bounty page",
     "score_breakdown": {"Audit Need": {"points": 5, "max": 25}, "Funding & Budget": {"points": 1, "max": 15}, "Category Fit": {"points": 12, "max": 15}, "Growth & Timing": {"points": 6, "max": 10}, "Verichains Moat": {"points": 3, "max": 5}, "Base Score": {"points": 23, "max": 30}},
     "pitch_services": ["Smart Contract Audit"], "funding": "TVL: $278", "tech": "EVM"},

    "Caddy Finance": {"score": 38, "priority": "LOW", "lead_group": "A",
     "summary": "Caddy Finance Bitcoin yield vaults ($94 TVL). Audited by Cairo Security Clan.",
     "audit_status": "✅ Audited by Cairo Security Clan",
     "score_breakdown": {"Audit Need": {"points": 4, "max": 25}, "Funding & Budget": {"points": 1, "max": 15}, "Category Fit": {"points": 8, "max": 15}, "Growth & Timing": {"points": 5, "max": 10}, "Verichains Moat": {"points": 2, "max": 5}, "Base Score": {"points": 18, "max": 30}},
     "pitch_services": ["Smart Contract Audit"], "funding": "TVL: $94", "tech": "Starknet (Cairo)"},

    "HoneyPlay Liquid Staking": {"score": 20, "priority": "LOW", "lead_group": "A",
     "summary": "HoneyPlay Liquid Staking ($9 TVL). Not viable.", "audit_status": "❌ No known public audit",
     "score_breakdown": {"Audit Need": {"points": 5, "max": 25}, "Funding & Budget": {"points": 1, "max": 15}, "Category Fit": {"points": 4, "max": 15}, "Growth & Timing": {"points": 1, "max": 10}, "Verichains Moat": {"points": 1, "max": 5}, "Base Score": {"points": 8, "max": 30}},
     "pitch_services": [], "funding": "TVL: $9", "tech": "Unknown"},

    "HoneyPlay AMM": {"score": 20, "priority": "LOW", "lead_group": "A",
     "summary": "HoneyPlay AMM ($0 TVL). Not viable.", "audit_status": "❌ No known public audit",
     "score_breakdown": {"Audit Need": {"points": 5, "max": 25}, "Funding & Budget": {"points": 1, "max": 15}, "Category Fit": {"points": 3, "max": 15}, "Growth & Timing": {"points": 1, "max": 10}, "Verichains Moat": {"points": 1, "max": 5}, "Base Score": {"points": 9, "max": 30}},
     "pitch_services": [], "funding": "TVL: $0", "tech": "Unknown"},

    "Avalon Superearn": {"score": 28, "priority": "LOW", "lead_group": "A",
     "summary": "Avalon Superearn yield ($897 TVL). Negligible.", "audit_status": "❌ No known public audit",
     "score_breakdown": {"Audit Need": {"points": 10, "max": 25}, "Funding & Budget": {"points": 1, "max": 15}, "Category Fit": {"points": 5, "max": 15}, "Growth & Timing": {"points": 3, "max": 10}, "Verichains Moat": {"points": 1, "max": 5}, "Base Score": {"points": 8, "max": 30}},
     "pitch_services": [], "funding": "TVL: $897", "tech": "Unknown"},

    "Nexion DEX": {"score": 22, "priority": "LOW", "lead_group": "A",
     "summary": "Nexion DEX ($80 TVL). Not viable.", "audit_status": "❌ No known public audit",
     "score_breakdown": {"Audit Need": {"points": 8, "max": 25}, "Funding & Budget": {"points": 1, "max": 15}, "Category Fit": {"points": 5, "max": 15}, "Growth & Timing": {"points": 2, "max": 10}, "Verichains Moat": {"points": 1, "max": 5}, "Base Score": {"points": 5, "max": 30}},
     "pitch_services": [], "funding": "TVL: $80", "tech": "Unknown"},

    "SomeSwap CL": {"score": 20, "priority": "LOW", "lead_group": "A",
     "summary": "SomeSwap CL ($15 TVL). Not viable.", "audit_status": "❌ No known public audit",
     "score_breakdown": {"Audit Need": {"points": 5, "max": 25}, "Funding & Budget": {"points": 1, "max": 15}, "Category Fit": {"points": 4, "max": 15}, "Growth & Timing": {"points": 1, "max": 10}, "Verichains Moat": {"points": 1, "max": 5}, "Base Score": {"points": 8, "max": 30}},
     "pitch_services": [], "funding": "TVL: $15", "tech": "Unknown"},

    "Shinjo": {"score": 20, "priority": "LOW", "lead_group": "A",
     "summary": "Shinjo yield lottery ($8 TVL). Not viable.", "audit_status": "❌ No known public audit",
     "score_breakdown": {"Audit Need": {"points": 5, "max": 25}, "Funding & Budget": {"points": 1, "max": 15}, "Category Fit": {"points": 3, "max": 15}, "Growth & Timing": {"points": 1, "max": 10}, "Verichains Moat": {"points": 1, "max": 5}, "Base Score": {"points": 9, "max": 30}},
     "pitch_services": [], "funding": "TVL: $8", "tech": "Unknown"},
}

# Build scores array with correct Vercel IDs
scores = []
missing = []
for name, data in score_data.items():
    if name in name_to_id:
        entry = {"id": name_to_id[name], "scored_by": "ai:antigravity", **data}
        scores.append(entry)
    else:
        missing.append(name)

if missing:
    print(f"⚠️  Missing on Vercel: {missing}")

print(f"Pushing {len(scores)} scores to Vercel...")
resp = requests.post(API, json={"scores": scores}, timeout=30)
print(f"Status: {resp.status_code}")
print(resp.json())
