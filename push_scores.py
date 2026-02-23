#!/usr/bin/env python3
"""Push Antigravity AI scores to LeadHunter API."""

import json, requests

API = "http://localhost:8000/api/leads/bulk-score"

scores = [
    {"id": 2, "score": 35, "priority": "LOW", "lead_group": "A",
     "summary": "Cooler Loans is Olympus DAO's protocol-native lending system. Multiple audits: Sherlock (Aug 2023), Nethermind Cooler V2, V2 Migrator reviews. TVL $196M is strong but already well-audited — low opportunity.",
     "audit_status": "✅ Audited by Sherlock (2023-08), Nethermind (Cooler V2) — docs.olympusdao.finance/security/audits",
     "score_breakdown": {"Audit Need": {"points": 3, "max": 25, "reason": "Multiple recent audits by Sherlock and Nethermind"}, "Funding & Budget": {"points": 12, "max": 15, "reason": "TVL $196M"}, "Category Fit": {"points": 10, "max": 15, "reason": "Lending"}, "Growth & Timing": {"points": 3, "max": 10, "reason": "Mature"}, "Verichains Moat": {"points": 2, "max": 5, "reason": "Standard DeFi"}, "Base Score": {"points": 5, "max": 30, "reason": "Low — saturated with auditors"}},
     "pitch_services": ["Smart Contract Audit"], "funding": "TVL: $196M — Olympus DAO treasury-backed", "tech": "Solidity, EVM (Ethereum)", "scored_by": "ai:antigravity"},

    {"id": 1, "score": 20, "priority": "LOW", "lead_group": "D",
     "summary": "Exod is a tokenized stock platform (Exodus Movement). SEC-compliant Class A shares on Algorand/Solana. Not a smart contract protocol — no audit needed.",
     "audit_status": "🚫 N/A — tokenized stock (SEC-regulated equity), not a smart contract protocol",
     "score_breakdown": {"Audit Need": {"points": 1, "max": 25, "reason": "Not a SC protocol"}, "Funding & Budget": {"points": 10, "max": 15, "reason": "NASDAQ: EXOD"}, "Category Fit": {"points": 2, "max": 15, "reason": "RWA/stock"}, "Growth & Timing": {"points": 2, "max": 10, "reason": "Established"}, "Verichains Moat": {"points": 1, "max": 5, "reason": "N/A"}, "Base Score": {"points": 4, "max": 30, "reason": "Not a viable lead"}},
     "pitch_services": [], "funding": "TVL: $291M — NASDAQ-listed", "tech": "Algorand, Solana", "scored_by": "ai:antigravity"},

    {"id": 4, "score": 55, "priority": "WARM", "lead_group": "A",
     "summary": "Tramplin.io is a Solana native staking pool ($12M TVL). Delegates to validators — no SC custody. No audit found. Could benefit from infra/pentest review.",
     "audit_status": "❌ No known public audit — Solana native staking (no SC custody)",
     "score_breakdown": {"Audit Need": {"points": 12, "max": 25, "reason": "No audit, Solana native staking"}, "Funding & Budget": {"points": 9, "max": 15, "reason": "TVL $12.3M"}, "Category Fit": {"points": 8, "max": 15, "reason": "Staking pool"}, "Growth & Timing": {"points": 6, "max": 10, "reason": "New listing"}, "Verichains Moat": {"points": 2, "max": 5, "reason": "Standard"}, "Base Score": {"points": 18, "max": 30, "reason": "Decent lead"}},
     "pitch_services": ["Penetration Testing", "Infrastructure Security Review"], "funding": "TVL: $12.3M", "tech": "Solana, native staking", "scored_by": "ai:antigravity"},

    {"id": 5, "score": 30, "priority": "LOW", "lead_group": "A",
     "summary": "Royco V2 yield marketplace ($7.7M TVL). Extensively audited by 6+ firms: Spearbit, Cantina, OtterSec, Zellic, Nethermind, yAudit. No opportunity.",
     "audit_status": "✅ Extensively audited by Spearbit, Cantina, OtterSec, Zellic, Nethermind, yAudit — docs.royco.org/audits",
     "score_breakdown": {"Audit Need": {"points": 2, "max": 25, "reason": "6+ auditors"}, "Funding & Budget": {"points": 8, "max": 15, "reason": "TVL $7.7M"}, "Category Fit": {"points": 8, "max": 15, "reason": "Yield"}, "Growth & Timing": {"points": 4, "max": 10, "reason": "Already audited"}, "Verichains Moat": {"points": 2, "max": 5, "reason": "Standard"}, "Base Score": {"points": 6, "max": 30, "reason": "No opportunity"}},
     "pitch_services": ["Smart Contract Audit"], "funding": "TVL: $7.7M", "tech": "Solidity, EVM, Cross-chain CCDM", "scored_by": "ai:antigravity"},

    {"id": 6, "score": 62, "priority": "WARM", "lead_group": "A",
     "summary": "EGAS Swap is part of ENI (Eniac Network), a modular L1. CertiK audit in progress. L1 + DEX combo is strong Verichains fit.",
     "audit_status": "⚠️ CertiK audit in progress for ENI ecosystem",
     "score_breakdown": {"Audit Need": {"points": 15, "max": 25, "reason": "CertiK in progress"}, "Funding & Budget": {"points": 8, "max": 15, "reason": "TVL $6.4M"}, "Category Fit": {"points": 12, "max": 15, "reason": "L1 + DEX"}, "Growth & Timing": {"points": 7, "max": 10, "reason": "Active"}, "Verichains Moat": {"points": 4, "max": 5, "reason": "L1 audit specialty"}, "Base Score": {"points": 16, "max": 30, "reason": "Good — L1 angle"}},
     "pitch_services": ["Blockchain L1 Audit", "Smart Contract Audit"], "funding": "TVL: $6.4M", "tech": "Modular L1 (ENI), EVM-compatible", "scored_by": "ai:antigravity"},

    {"id": 8, "score": 40, "priority": "MONITOR", "lead_group": "A",
     "summary": "TokenLabs IOTA liquid staking ($625K TVL). Audited by AuditOne (100% security), SolidProof, MoveBit. Low opportunity.",
     "audit_status": "✅ Audited by AuditOne, SolidProof, MoveBit",
     "score_breakdown": {"Audit Need": {"points": 4, "max": 25, "reason": "3 audits completed"}, "Funding & Budget": {"points": 5, "max": 15, "reason": "TVL $625K"}, "Category Fit": {"points": 10, "max": 15, "reason": "Liquid staking"}, "Growth & Timing": {"points": 5, "max": 10, "reason": "New"}, "Verichains Moat": {"points": 2, "max": 5, "reason": "IOTA"}, "Base Score": {"points": 14, "max": 30, "reason": "Already audited"}},
     "pitch_services": ["Smart Contract Audit"], "funding": "TVL: $625K", "tech": "IOTA, ERC20", "scored_by": "ai:antigravity"},

    {"id": 9, "score": 42, "priority": "MONITOR", "lead_group": "A",
     "summary": "atomiq exchange is a cross-chain atomic swap bridge ($243K TVL). Audited by Ackee Blockchain (Dec 2023, re-audit Jan 2024). Bridge category = high risk but already audited.",
     "audit_status": "✅ Audited by Ackee Blockchain (Dec 2023, re-audit Jan 2024) — github.com/atomiqlabs",
     "score_breakdown": {"Audit Need": {"points": 8, "max": 25, "reason": "~1yr old audit, bridges need re-audits"}, "Funding & Budget": {"points": 4, "max": 15, "reason": "TVL $243K"}, "Category Fit": {"points": 14, "max": 15, "reason": "Cross-chain bridge — highest need"}, "Growth & Timing": {"points": 5, "max": 10, "reason": "Active"}, "Verichains Moat": {"points": 3, "max": 5, "reason": "Cross-chain"}, "Base Score": {"points": 8, "max": 30, "reason": "Good category, small TVL"}},
     "pitch_services": ["Smart Contract Audit", "Cryptography Audit"], "funding": "TVL: $243K", "tech": "Solana, Bitcoin, atomic swaps", "scored_by": "ai:antigravity"},

    {"id": 10, "score": 60, "priority": "WARM", "lead_group": "A",
     "summary": "Spreads Finance yield protocol ($193K TVL). No public audit found. Yield protocol handling funds without audit — clear vulnerability.",
     "audit_status": "❌ No known public audit",
     "score_breakdown": {"Audit Need": {"points": 22, "max": 25, "reason": "No audit — handles user funds"}, "Funding & Budget": {"points": 3, "max": 15, "reason": "TVL $193K"}, "Category Fit": {"points": 10, "max": 15, "reason": "Yield"}, "Growth & Timing": {"points": 7, "max": 10, "reason": "New"}, "Verichains Moat": {"points": 2, "max": 5, "reason": "Standard"}, "Base Score": {"points": 16, "max": 30, "reason": "Good need, small project"}},
     "pitch_services": ["Smart Contract Audit"], "funding": "TVL: $193K", "tech": "EVM", "scored_by": "ai:antigravity"},

    {"id": 11, "score": 65, "priority": "WARM", "lead_group": "A",
     "summary": "Zentra Finance lending on Citrea (Bitcoin ZK rollup), Aave fork. Under audit per website. ZK rollup + lending = strong Verichains fit.",
     "audit_status": "⚠️ Under audit (per zentra.finance) — no completed report yet",
     "score_breakdown": {"Audit Need": {"points": 18, "max": 25, "reason": "Under audit, not complete"}, "Funding & Budget": {"points": 3, "max": 15, "reason": "TVL $176K"}, "Category Fit": {"points": 13, "max": 15, "reason": "Lending on ZK rollup"}, "Growth & Timing": {"points": 8, "max": 10, "reason": "Actively seeking audit"}, "Verichains Moat": {"points": 4, "max": 5, "reason": "ZK rollup — Verichains specialty"}, "Base Score": {"points": 19, "max": 30, "reason": "Strong — ZK + lending + seeking audit"}},
     "pitch_services": ["Smart Contract Audit", "Cryptography Audit (ZK)"], "funding": "TVL: $176K", "tech": "Citrea (Bitcoin ZK rollup), Aave fork", "scored_by": "ai:antigravity"},

    {"id": 13, "score": 55, "priority": "WARM", "lead_group": "A",
     "summary": "Alphix DEX ($124K TVL). No audit — Hook v2 audit planned Q2 2026. Good timing to pitch before they select auditor.",
     "audit_status": "❌ No audit — Hook v2 audit planned for Q2 2026",
     "score_breakdown": {"Audit Need": {"points": 22, "max": 25, "reason": "Planning audit — perfect timing"}, "Funding & Budget": {"points": 3, "max": 15, "reason": "TVL $124K"}, "Category Fit": {"points": 10, "max": 15, "reason": "DEX"}, "Growth & Timing": {"points": 8, "max": 10, "reason": "Actively planning audit"}, "Verichains Moat": {"points": 2, "max": 5, "reason": "Standard"}, "Base Score": {"points": 10, "max": 30, "reason": "Good timing, small project"}},
     "pitch_services": ["Smart Contract Audit"], "funding": "TVL: $124K", "tech": "EVM", "scored_by": "ai:antigravity"},

    {"id": 7, "score": 62, "priority": "WARM", "lead_group": "A",
     "summary": "Paimon Finance RWA tokenization on BNB Chain ($753K TVL). BNB MVB S8 + YZi Labs incubation. No audit found. RWA compliance = high audit need.",
     "audit_status": "❌ No known public audit — partner MyStonks has CertiK audit (Sep 2025)",
     "score_breakdown": {"Audit Need": {"points": 22, "max": 25, "reason": "No audit — RWA needs compliance review"}, "Funding & Budget": {"points": 6, "max": 15, "reason": "TVL $753K, accelerator backing"}, "Category Fit": {"points": 13, "max": 15, "reason": "RWA — high compliance need"}, "Growth & Timing": {"points": 7, "max": 10, "reason": "Accelerator-backed"}, "Verichains Moat": {"points": 2, "max": 5, "reason": "Standard RWA"}, "Base Score": {"points": 12, "max": 30, "reason": "Good — RWA + no audit + accelerator"}},
     "pitch_services": ["Smart Contract Audit", "Penetration Testing"], "funding": "TVL: $753K, BNB MVB S8 + YZi Labs", "tech": "BNB Chain, RWA", "scored_by": "ai:antigravity"},

    {"id": 12, "score": 40, "priority": "MONITOR", "lead_group": "A",
     "summary": "Alpaca Dex on Keeta ($138K TVL). Off-chain liquidity — SC not deployed yet. Future opportunity when Keeta SC layer launches.",
     "audit_status": "❌ No SC deployed — off-chain management, plans to deploy on Keeta SC layer",
     "score_breakdown": {"Audit Need": {"points": 15, "max": 25, "reason": "No SC yet"}, "Funding & Budget": {"points": 3, "max": 15, "reason": "TVL $138K"}, "Category Fit": {"points": 8, "max": 15, "reason": "DEX"}, "Growth & Timing": {"points": 5, "max": 10, "reason": "Pre-SC"}, "Verichains Moat": {"points": 2, "max": 5, "reason": "Standard"}, "Base Score": {"points": 7, "max": 30, "reason": "Monitor for SC deployment"}},
     "pitch_services": ["Smart Contract Audit"], "funding": "TVL: $138K", "tech": "Keeta blockchain", "scored_by": "ai:antigravity"},

    {"id": 3, "score": 38, "priority": "LOW", "lead_group": "D",
     "summary": "Stobox tokenization services ($23M TVL). CertiK audited. Services/compliance focus — not typical SC audit target.",
     "audit_status": "✅ CertiK audit completed for Stobox Exchange",
     "score_breakdown": {"Audit Need": {"points": 4, "max": 25, "reason": "CertiK audited"}, "Funding & Budget": {"points": 10, "max": 15, "reason": "TVL $23M"}, "Category Fit": {"points": 5, "max": 15, "reason": "Services"}, "Growth & Timing": {"points": 3, "max": 10, "reason": "Established"}, "Verichains Moat": {"points": 1, "max": 5, "reason": "N/A"}, "Base Score": {"points": 15, "max": 30, "reason": "Low opportunity"}},
     "pitch_services": ["Smart Contract Audit"], "funding": "TVL: $23M", "tech": "EVM, Stobox DID", "scored_by": "ai:antigravity"},

    {"id": 14, "score": 42, "priority": "MONITOR", "lead_group": "A",
     "summary": "Murphy DEX ($89K TVL). No info found — no website or GitHub. Opaque project.",
     "audit_status": "❌ No known public audit",
     "score_breakdown": {"Audit Need": {"points": 18, "max": 25, "reason": "No audit"}, "Funding & Budget": {"points": 2, "max": 15, "reason": "TVL $89K"}, "Category Fit": {"points": 8, "max": 15, "reason": "DEX"}, "Growth & Timing": {"points": 4, "max": 10, "reason": "Tiny"}, "Verichains Moat": {"points": 1, "max": 5, "reason": "Unknown"}, "Base Score": {"points": 9, "max": 30, "reason": "Too small"}},
     "pitch_services": ["Smart Contract Audit"], "funding": "TVL: $89K", "tech": "Unknown", "scored_by": "ai:antigravity"},

    {"id": 16, "score": 40, "priority": "MONITOR", "lead_group": "A",
     "summary": "Stone Vault (stva.io) yield aggregator ($52K TVL). StakeStone ecosystem audited by Quantstamp + Veridise.",
     "audit_status": "⚠️ StakeStone ecosystem audited by Quantstamp + Veridise — stva.io specific status unclear",
     "score_breakdown": {"Audit Need": {"points": 12, "max": 25, "reason": "Ecosystem audited"}, "Funding & Budget": {"points": 2, "max": 15, "reason": "TVL $52K"}, "Category Fit": {"points": 8, "max": 15, "reason": "Yield"}, "Growth & Timing": {"points": 5, "max": 10, "reason": "New"}, "Verichains Moat": {"points": 2, "max": 5, "reason": "Standard"}, "Base Score": {"points": 11, "max": 30, "reason": "Small, may be covered"}},
     "pitch_services": ["Smart Contract Audit"], "funding": "TVL: $52K", "tech": "EVM", "scored_by": "ai:antigravity"},

    {"id": 17, "score": 50, "priority": "MONITOR", "lead_group": "A",
     "summary": "Normal Finance derivatives/index on Stellar ($33K TVL). Claims audited but no report found.",
     "audit_status": "⚠️ Claims audited per normalfinance.io — no public report found",
     "score_breakdown": {"Audit Need": {"points": 15, "max": 25, "reason": "Claims audited, unverifiable"}, "Funding & Budget": {"points": 2, "max": 15, "reason": "TVL $33K"}, "Category Fit": {"points": 10, "max": 15, "reason": "Derivatives"}, "Growth & Timing": {"points": 5, "max": 10, "reason": "New"}, "Verichains Moat": {"points": 2, "max": 5, "reason": "Stellar"}, "Base Score": {"points": 16, "max": 30, "reason": "Interesting but tiny"}},
     "pitch_services": ["Smart Contract Audit"], "funding": "TVL: $33K", "tech": "Stellar", "scored_by": "ai:antigravity"},

    {"id": 15, "score": 52, "priority": "MONITOR", "lead_group": "A",
     "summary": "DeltaDeFi DEX on Cardano ($80K TVL). Related DeltaTrade audited by BlockSec — 10 High + 9 Medium issues. Needs re-verification.",
     "audit_status": "⚠️ DeltaTrade audited by BlockSec — 10 High + 9 Medium risk issues found",
     "score_breakdown": {"Audit Need": {"points": 18, "max": 25, "reason": "Previous audit found many issues"}, "Funding & Budget": {"points": 2, "max": 15, "reason": "TVL $80K"}, "Category Fit": {"points": 8, "max": 15, "reason": "Cardano DEX"}, "Growth & Timing": {"points": 5, "max": 10, "reason": "Needs follow-up"}, "Verichains Moat": {"points": 3, "max": 5, "reason": "Cardano"}, "Base Score": {"points": 16, "max": 30, "reason": "Past issues interesting"}},
     "pitch_services": ["Smart Contract Audit"], "funding": "TVL: $80K", "tech": "Cardano", "scored_by": "ai:antigravity"},

    {"id": 19, "score": 25, "priority": "LOW", "lead_group": "A",
     "summary": "ETMCv2 DEX ($1.7K TVL). Negligible. Not viable.",
     "audit_status": "❌ No known public audit",
     "score_breakdown": {"Audit Need": {"points": 10, "max": 25, "reason": "No audit"}, "Funding & Budget": {"points": 1, "max": 15, "reason": "$1.7K"}, "Category Fit": {"points": 5, "max": 15, "reason": "DEX"}, "Growth & Timing": {"points": 2, "max": 10, "reason": "None"}, "Verichains Moat": {"points": 1, "max": 5, "reason": "Unknown"}, "Base Score": {"points": 6, "max": 30, "reason": "Not viable"}},
     "pitch_services": [], "funding": "TVL: $1.7K", "tech": "ETCMC", "scored_by": "ai:antigravity"},

    {"id": 20, "score": 25, "priority": "LOW", "lead_group": "A",
     "summary": "Nexion Vaults ($1K TVL). Negligible. Not viable.",
     "audit_status": "❌ No known public audit",
     "score_breakdown": {"Audit Need": {"points": 10, "max": 25, "reason": "No audit"}, "Funding & Budget": {"points": 1, "max": 15, "reason": "$1K"}, "Category Fit": {"points": 5, "max": 15, "reason": "Yield"}, "Growth & Timing": {"points": 2, "max": 10, "reason": "None"}, "Verichains Moat": {"points": 1, "max": 5, "reason": "Standard"}, "Base Score": {"points": 6, "max": 30, "reason": "Not viable"}},
     "pitch_services": [], "funding": "TVL: $1K", "tech": "Unknown", "scored_by": "ai:antigravity"},

    {"id": 22, "score": 22, "priority": "LOW", "lead_group": "A",
     "summary": "OK-BITOK Vault ($611 TVL). Negligible. Not viable.",
     "audit_status": "❌ No known public audit",
     "score_breakdown": {"Audit Need": {"points": 8, "max": 25, "reason": "No audit"}, "Funding & Budget": {"points": 1, "max": 15, "reason": "$611"}, "Category Fit": {"points": 4, "max": 15, "reason": "Yield"}, "Growth & Timing": {"points": 2, "max": 10, "reason": "None"}, "Verichains Moat": {"points": 1, "max": 5, "reason": "Standard"}, "Base Score": {"points": 6, "max": 30, "reason": "Not viable"}},
     "pitch_services": [], "funding": "TVL: $611", "tech": "Unknown", "scored_by": "ai:antigravity"},

    {"id": 23, "score": 50, "priority": "MONITOR", "lead_group": "A",
     "summary": "Floe Labs — first Credit DEX, intent-based lending ($278 TVL). Audited + Immunefi bug bounty. Novel design but tiny TVL.",
     "audit_status": "✅ Audited — report via Immunefi bug bounty page",
     "score_breakdown": {"Audit Need": {"points": 5, "max": 25, "reason": "Audited + bug bounty"}, "Funding & Budget": {"points": 1, "max": 15, "reason": "$278"}, "Category Fit": {"points": 12, "max": 15, "reason": "Novel lending"}, "Growth & Timing": {"points": 6, "max": 10, "reason": "Pre-growth"}, "Verichains Moat": {"points": 3, "max": 5, "reason": "Intent-based"}, "Base Score": {"points": 23, "max": 30, "reason": "Novel but audited"}},
     "pitch_services": ["Smart Contract Audit"], "funding": "TVL: $278", "tech": "EVM, intent-based", "scored_by": "ai:antigravity"},

    {"id": 25, "score": 38, "priority": "LOW", "lead_group": "A",
     "summary": "Caddy Finance Bitcoin yield vaults ($94 TVL). Audited by Cairo Security Clan. Negligible TVL.",
     "audit_status": "✅ Audited by Cairo Security Clan",
     "score_breakdown": {"Audit Need": {"points": 4, "max": 25, "reason": "Audited"}, "Funding & Budget": {"points": 1, "max": 15, "reason": "$94"}, "Category Fit": {"points": 8, "max": 15, "reason": "BTC yield"}, "Growth & Timing": {"points": 5, "max": 10, "reason": "Early"}, "Verichains Moat": {"points": 2, "max": 5, "reason": "Starknet"}, "Base Score": {"points": 18, "max": 30, "reason": "Audited, negligible TVL"}},
     "pitch_services": ["Smart Contract Audit"], "funding": "TVL: $94", "tech": "Starknet (Cairo)", "scored_by": "ai:antigravity"},

    {"id": 28, "score": 20, "priority": "LOW", "lead_group": "A",
     "summary": "HoneyPlay Liquid Staking ($9 TVL). Zero activity. Not viable.",
     "audit_status": "❌ No known public audit",
     "score_breakdown": {"Audit Need": {"points": 5, "max": 25, "reason": "No audit"}, "Funding & Budget": {"points": 1, "max": 15, "reason": "$9"}, "Category Fit": {"points": 4, "max": 15, "reason": "Liquid staking"}, "Growth & Timing": {"points": 1, "max": 10, "reason": "Dead"}, "Verichains Moat": {"points": 1, "max": 5, "reason": "Standard"}, "Base Score": {"points": 8, "max": 30, "reason": "Not viable"}},
     "pitch_services": [], "funding": "TVL: $9", "tech": "Unknown", "scored_by": "ai:antigravity"},

    {"id": 30, "score": 20, "priority": "LOW", "lead_group": "A",
     "summary": "HoneyPlay AMM ($0 TVL). Zero activity. Not viable.",
     "audit_status": "❌ No known public audit",
     "score_breakdown": {"Audit Need": {"points": 5, "max": 25, "reason": "No audit"}, "Funding & Budget": {"points": 1, "max": 15, "reason": "$0"}, "Category Fit": {"points": 3, "max": 15, "reason": "DEX"}, "Growth & Timing": {"points": 1, "max": 10, "reason": "Dead"}, "Verichains Moat": {"points": 1, "max": 5, "reason": "Standard"}, "Base Score": {"points": 9, "max": 30, "reason": "Not viable"}},
     "pitch_services": [], "funding": "TVL: $0", "tech": "Unknown", "scored_by": "ai:antigravity"},

    {"id": 18, "score": 22, "priority": "LOW", "lead_group": "A",
     "summary": "Parity DEX CL ($1.9K TVL). Not related to Parity Technologies. Negligible.",
     "audit_status": "❌ No known public audit",
     "score_breakdown": {"Audit Need": {"points": 8, "max": 25, "reason": "No audit"}, "Funding & Budget": {"points": 1, "max": 15, "reason": "$1.9K"}, "Category Fit": {"points": 5, "max": 15, "reason": "DEX"}, "Growth & Timing": {"points": 2, "max": 10, "reason": "None"}, "Verichains Moat": {"points": 1, "max": 5, "reason": "Standard"}, "Base Score": {"points": 5, "max": 30, "reason": "Not viable"}},
     "pitch_services": [], "funding": "TVL: $1.9K", "tech": "Unknown", "scored_by": "ai:antigravity"},

    {"id": 21, "score": 28, "priority": "LOW", "lead_group": "A",
     "summary": "Avalon Superearn yield ($897 TVL). Avalon Finance sub-product. Negligible.",
     "audit_status": "❌ No known public audit for this specific product",
     "score_breakdown": {"Audit Need": {"points": 10, "max": 25, "reason": "No audit"}, "Funding & Budget": {"points": 1, "max": 15, "reason": "$897"}, "Category Fit": {"points": 5, "max": 15, "reason": "Yield"}, "Growth & Timing": {"points": 3, "max": 10, "reason": "Early"}, "Verichains Moat": {"points": 1, "max": 5, "reason": "Standard"}, "Base Score": {"points": 8, "max": 30, "reason": "Too small"}},
     "pitch_services": [], "funding": "TVL: $897", "tech": "Unknown", "scored_by": "ai:antigravity"},

    {"id": 24, "score": 22, "priority": "LOW", "lead_group": "A",
     "summary": "Parity DEX ($101 TVL). Negligible.",
     "audit_status": "❌ No known public audit",
     "score_breakdown": {"Audit Need": {"points": 8, "max": 25, "reason": "No audit"}, "Funding & Budget": {"points": 1, "max": 15, "reason": "$101"}, "Category Fit": {"points": 5, "max": 15, "reason": "DEX"}, "Growth & Timing": {"points": 2, "max": 10, "reason": "None"}, "Verichains Moat": {"points": 1, "max": 5, "reason": "Standard"}, "Base Score": {"points": 5, "max": 30, "reason": "Not viable"}},
     "pitch_services": [], "funding": "TVL: $101", "tech": "Unknown", "scored_by": "ai:antigravity"},

    {"id": 26, "score": 22, "priority": "LOW", "lead_group": "A",
     "summary": "Nexion DEX ($80 TVL). Negligible.",
     "audit_status": "❌ No known public audit",
     "score_breakdown": {"Audit Need": {"points": 8, "max": 25, "reason": "No audit"}, "Funding & Budget": {"points": 1, "max": 15, "reason": "$80"}, "Category Fit": {"points": 5, "max": 15, "reason": "DEX"}, "Growth & Timing": {"points": 2, "max": 10, "reason": "None"}, "Verichains Moat": {"points": 1, "max": 5, "reason": "Standard"}, "Base Score": {"points": 5, "max": 30, "reason": "Not viable"}},
     "pitch_services": [], "funding": "TVL: $80", "tech": "Unknown", "scored_by": "ai:antigravity"},

    {"id": 27, "score": 20, "priority": "LOW", "lead_group": "A",
     "summary": "SomeSwap CL ($15 TVL). Negligible.",
     "audit_status": "❌ No known public audit",
     "score_breakdown": {"Audit Need": {"points": 5, "max": 25, "reason": "No audit"}, "Funding & Budget": {"points": 1, "max": 15, "reason": "$15"}, "Category Fit": {"points": 4, "max": 15, "reason": "DEX"}, "Growth & Timing": {"points": 1, "max": 10, "reason": "Dead"}, "Verichains Moat": {"points": 1, "max": 5, "reason": "Standard"}, "Base Score": {"points": 8, "max": 30, "reason": "Not viable"}},
     "pitch_services": [], "funding": "TVL: $15", "tech": "Unknown", "scored_by": "ai:antigravity"},

    {"id": 29, "score": 20, "priority": "LOW", "lead_group": "A",
     "summary": "Shinjo yield lottery ($8 TVL). Negligible.",
     "audit_status": "❌ No known public audit",
     "score_breakdown": {"Audit Need": {"points": 5, "max": 25, "reason": "No audit"}, "Funding & Budget": {"points": 1, "max": 15, "reason": "$8"}, "Category Fit": {"points": 3, "max": 15, "reason": "Lottery"}, "Growth & Timing": {"points": 1, "max": 10, "reason": "Dead"}, "Verichains Moat": {"points": 1, "max": 5, "reason": "Standard"}, "Base Score": {"points": 9, "max": 30, "reason": "Not viable"}},
     "pitch_services": [], "funding": "TVL: $8", "tech": "Unknown", "scored_by": "ai:antigravity"},
]

print(f"Pushing {len(scores)} scores to {API}...")
resp = requests.post(API, json={"scores": scores}, timeout=30)
print(f"Status: {resp.status_code}")
print(resp.json())
