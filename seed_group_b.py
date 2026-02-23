"""
Seed Group B Watchlist — Mid-cap DeFi on Emerging Chains + Multichain Expansion
Based on criteria:
  1. Mid-cap TVL ($10M - $500M) on emerging chains (Monad, Berachain, Movement, Sonic, Sei, Sui)
  2. Multichain expansion (deploying on new chains = new code = needs audit)
  3. Funding sweet spot ($1.5M - $5M)

Run once to populate watchlist, then user can manually edit/add via UI.
"""

import database as db

GROUP_B_SEED = [
    # ---- Criteria 2: Mid-cap on Emerging Chains ----
    {
        "name": "Curvance",
        "github_repo": "https://github.com/curvance/curvance-contracts",
        "snapshot_space": "",
        "x_account": "https://x.com/curvance",
        "category": "Lending",
        "client_type": "Mid-cap Emerging",
        "notes": "Lending/Yield on Monad, Base. TVL growing. Raised $3.6M. Audit needed for Monad deployment.",
        "auditor": "",
        "last_audit_date": "",
    },
    {
        "name": "Infrared Finance",
        "github_repo": "https://github.com/infrared-finance",
        "snapshot_space": "",
        "x_account": "https://x.com/InfraredFinance",
        "category": "Liquid Staking",
        "client_type": "Mid-cap Emerging",
        "notes": "Liquid staking on Berachain. TVL ~$300M+. Native BGT staking. New ecosystem.",
        "auditor": "",
        "last_audit_date": "",
    },
    {
        "name": "Kodiak Finance",
        "github_repo": "https://github.com/kodiak-finance",
        "snapshot_space": "",
        "x_account": "https://x.com/KodiakFi",
        "category": "DEX",
        "client_type": "Mid-cap Emerging",
        "notes": "DEX on Berachain. Native AMM. New chain = new contracts.",
        "auditor": "",
        "last_audit_date": "",
    },
    {
        "name": "Kuru Exchange",
        "github_repo": "https://github.com/kuru-exchange",
        "snapshot_space": "",
        "x_account": "https://x.com/KuruExchange",
        "category": "DEX",
        "client_type": "Mid-cap Emerging",
        "notes": "On-chain order book DEX on Monad. Raised $2M. Novel architecture, needs audit.",
        "auditor": "",
        "last_audit_date": "",
    },
    {
        "name": "Ambient Finance",
        "github_repo": "https://github.com/CrocSwap/CrocSwap-protocol",
        "snapshot_space": "",
        "x_account": "https://x.com/ambient_finance",
        "category": "DEX",
        "client_type": "Mid-cap Multichain",
        "notes": "DEX expanding to Monad, Scroll, Blast. Single-contract AMM. Multichain = multiple deployments.",
        "auditor": "",
        "last_audit_date": "",
    },
    {
        "name": "Beets (Beethoven X)",
        "github_repo": "https://github.com/beethovenxfi",
        "snapshot_space": "beets.eth",
        "x_account": "https://x.com/beethaborern_x",
        "category": "DEX",
        "client_type": "Mid-cap Multichain",
        "notes": "Balancer-based DEX on Sonic, Optimism. Expanding chains. TVL ~$100M+.",
        "auditor": "",
        "last_audit_date": "",
    },
    {
        "name": "Shadow Exchange",
        "github_repo": "https://github.com/shadow-exchange",
        "snapshot_space": "",
        "x_account": "https://x.com/ShadowDEX_",
        "category": "DEX",
        "client_type": "Mid-cap Emerging",
        "notes": "ve(3,3) DEX on Sonic chain. TVL growing rapidly. New chain deployment.",
        "auditor": "",
        "last_audit_date": "",
    },
    {
        "name": "Silo Finance",
        "github_repo": "https://github.com/silo-finance/silo-core-v1",
        "snapshot_space": "silo.eth",
        "x_account": "https://x.com/SiloFinance",
        "category": "Lending",
        "client_type": "Mid-cap Multichain",
        "notes": "Isolated lending on Arbitrum, Sonic, Base. V2 upgrade. Multichain expansion. TVL ~$200M+.",
        "auditor": "",
        "last_audit_date": "",
    },
    {
        "name": "Meridian Finance",
        "github_repo": "https://github.com/meridianfinance",
        "snapshot_space": "",
        "x_account": "https://x.com/meridaboranfi",
        "category": "Lending",
        "client_type": "Mid-cap Emerging",
        "notes": "Lending on Movement chain. New ecosystem. Needs audit for new chain code.",
        "auditor": "",
        "last_audit_date": "",
    },
    {
        "name": "NAVI Protocol",
        "github_repo": "https://github.com/naviprotocol",
        "snapshot_space": "",
        "x_account": "https://x.com/naboravi_protocol",
        "category": "Lending",
        "client_type": "Mid-cap Emerging",
        "notes": "Lending/Borrowing on Sui. TVL ~$300M+. Move language. Needs specialized audit.",
        "auditor": "",
        "last_audit_date": "",
    },
    {
        "name": "Scallop Lend",
        "github_repo": "https://github.com/scallop-io",
        "snapshot_space": "",
        "x_account": "https://x.com/Scallop_io",
        "category": "Lending",
        "client_type": "Mid-cap Emerging",
        "notes": "Lending on Sui. TVL ~$150M+. Move language smart contracts. Sui ecosystem growth.",
        "auditor": "",
        "last_audit_date": "",
    },
    {
        "name": "Cetus Protocol",
        "github_repo": "https://github.com/CetusProtocol",
        "snapshot_space": "",
        "x_account": "https://x.com/CetusProtocol",
        "category": "DEX",
        "client_type": "Mid-cap Multichain",
        "notes": "CLMM DEX on Sui + Aptos. Move language. Multichain. Needs re-audit for updates.",
        "auditor": "",
        "last_audit_date": "",
    },
    {
        "name": "Aftermath Finance",
        "github_repo": "https://github.com/AftermathFinance",
        "snapshot_space": "",
        "x_account": "https://x.com/AftermathFi",
        "category": "DEX",
        "client_type": "Mid-cap Emerging",
        "notes": "DEX + Liquid Staking on Sui. TVL ~$100M+. Move language.",
        "auditor": "",
        "last_audit_date": "",
    },

    # ---- Criteria 3: Multichain Expansion (existing protocols deploying on new chains) ----
    {
        "name": "Stargate Finance",
        "github_repo": "https://github.com/stargate-protocol/stargate-v2",
        "snapshot_space": "stgdao.eth",
        "x_account": "https://x.com/StargateFinance",
        "category": "Bridge",
        "client_type": "Multichain Expansion",
        "notes": "LayerZero bridge. V2 upgrade deployed across 15+ chains. Each chain = new deployment to audit.",
        "auditor": "Multiple",
        "last_audit_date": "2024",
    },
    {
        "name": "Gains Network (gTrade)",
        "github_repo": "https://github.com/GainsNetwork-org/gTrade-contracts",
        "snapshot_space": "gainsdao.eth",
        "x_account": "https://x.com/GainsNetwork_io",
        "category": "Derivatives",
        "client_type": "Multichain Expansion",
        "notes": "Perpetual DEX on Polygon, Arbitrum, Base. Expanding to more chains. V9+ upgrades.",
        "auditor": "",
        "last_audit_date": "",
    },
    {
        "name": "Radiant Capital",
        "github_repo": "https://github.com/radiant-capital",
        "snapshot_space": "radiantcapital.eth",
        "x_account": "https://x.com/RDNTCapital",
        "category": "Lending",
        "client_type": "Multichain Expansion",
        "notes": "Cross-chain lending. Was hacked Oct 2024 ($50M). Rebuilding = needs comprehensive re-audit.",
        "auditor": "",
        "last_audit_date": "",
    },
    {
        "name": "Thala Labs",
        "github_repo": "https://github.com/ThalaLabs",
        "snapshot_space": "",
        "x_account": "https://x.com/ThalaLabs",
        "category": "DEX",
        "client_type": "Mid-cap Emerging",
        "notes": "DEX + CDP on Aptos. Move language. ThalaSwap + MOD stablecoin. TVL ~$100M+.",
        "auditor": "",
        "last_audit_date": "",
    },
    {
        "name": "Echelon Market",
        "github_repo": "https://github.com/echelon-market",
        "snapshot_space": "",
        "x_account": "https://x.com/EchelonMarket",
        "category": "Lending",
        "client_type": "Mid-cap Emerging",
        "notes": "Lending on Aptos + Movement. Move language. Deploying on new chains.",
        "auditor": "",
        "last_audit_date": "",
    },
    {
        "name": "Kinza Finance",
        "github_repo": "https://github.com/kinza-finance",
        "snapshot_space": "",
        "x_account": "https://x.com/KinzaFinance",
        "category": "Lending",
        "client_type": "Mid-cap Multichain",
        "notes": "Lending on BNB Chain, opBNB. Fork of Aave V3. Growing TVL. Re-audit recommended.",
        "auditor": "",
        "last_audit_date": "",
    },
]


def seed():
    conn = db.get_conn()
    db.init_tables(conn)

    existing = {r["name"] for r in db.get_watchlist() if hasattr(r, '__getitem__')}

    added = 0
    skipped = 0
    for project in GROUP_B_SEED:
        if project["name"] in existing:
            print(f"  ⏭️  {project['name']} already in watchlist")
            skipped += 1
            continue

        try:
            db.insert_watchlist(project)
            added += 1
            print(f"  ✅ Added: {project['name']} ({project['client_type']})")
        except Exception as e:
            print(f"  ❌ Failed: {project['name']} — {e}")
            skipped += 1

    print(f"\n{'='*50}")
    print(f"📊 Group B Seed Summary")
    print(f"  ✅ Added: {added}")
    print(f"  ⏭️  Skipped: {skipped}")
    print(f"  📋 Total in watchlist: {len(db.get_watchlist())}")


if __name__ == "__main__":
    seed()
