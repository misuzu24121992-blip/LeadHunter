"""
On-chain Upgraded() Event Monitor — Phase 2
Polls free Etherscan-like APIs for EIP-1967 Upgraded(address) events on proxy contracts.

EIP-1967 Upgraded event signature:
  event Upgraded(address indexed implementation)
  topic0 = 0xbc7cd75a20ee27fd9adebab32041f755214dbc6bf63e2c4e82a1d7b0add4f783

Free tier limits:
  - Etherscan: 5 calls/sec, no key needed (with key: 5/sec per chain)
  - Basescan, Arbiscan, etc: same model
  - We poll every 6h via cron → ~4 API calls per scan = well within limits

Cost: $0/month
"""

import json
import os
import time
from datetime import datetime, timezone

import requests

# ---- Etherscan-like API endpoints (free tier) ----
CHAIN_APIS = {
    "ethereum": {
        "url": "https://api.etherscan.io/api",
        "key_env": "ETHERSCAN_API_KEY",
        "explorer": "https://etherscan.io",
    },
    "arbitrum": {
        "url": "https://api.arbiscan.io/api",
        "key_env": "ARBISCAN_API_KEY",
        "explorer": "https://arbiscan.io",
    },
    "base": {
        "url": "https://api.basescan.org/api",
        "key_env": "BASESCAN_API_KEY",
        "explorer": "https://basescan.org",
    },
    "optimism": {
        "url": "https://api-optimistic.etherscan.io/api",
        "key_env": "OPTIMISM_API_KEY",
        "explorer": "https://optimistic.etherscan.io",
    },
    "polygon": {
        "url": "https://api.polygonscan.com/api",
        "key_env": "POLYGONSCAN_API_KEY",
        "explorer": "https://polygonscan.com",
    },
    "bsc": {
        "url": "https://api.bscscan.com/api",
        "key_env": "BSCSCAN_API_KEY",
        "explorer": "https://bscscan.com",
    },
    "avalanche": {
        "url": "https://api.snowscan.xyz/api",
        "key_env": "SNOWSCAN_API_KEY",
        "explorer": "https://snowscan.xyz",
    },
    "sonic": {
        "url": "https://api.sonicscan.org/api",
        "key_env": "SONICSCAN_API_KEY",
        "explorer": "https://sonicscan.org",
    },
}

# EIP-1967 Upgraded(address indexed implementation) event topic
UPGRADED_TOPIC = "0xbc7cd75a20ee27fd9adebab32041f755214dbc6bf63e2c4e82a1d7b0add4f783"

# State file for tracking last-seen blocks
_state_dir = "/tmp" if os.environ.get("VERCEL") else os.path.dirname(__file__)
STATE_FILE = os.path.join(_state_dir, "onchain_state.json")


def _load_state() -> dict:
    """Load last-scanned block numbers per chain/address."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_state(state: dict):
    """Persist state."""
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"  [OnChain] ⚠️  Failed to save state: {e}")


def _get_api_key(chain: str) -> str:
    """Get API key for a chain, empty string if not set (still works, just rate-limited)."""
    config = CHAIN_APIS.get(chain, {})
    key_env = config.get("key_env", "")
    return os.environ.get(key_env, "")


def _get_latest_block(chain: str) -> int | None:
    """Get the latest block number for a chain."""
    config = CHAIN_APIS.get(chain)
    if not config:
        return None

    api_key = _get_api_key(chain)
    params = {
        "module": "proxy",
        "action": "eth_blockNumber",
    }
    if api_key:
        params["apikey"] = api_key

    try:
        resp = requests.get(config["url"], params=params, timeout=10)
        data = resp.json()
        hex_block = data.get("result", "0x0")
        return int(hex_block, 16)
    except Exception as e:
        print(f"  [OnChain] ⚠️  Failed to get latest block for {chain}: {e}")
        return None


def _get_upgrade_events(chain: str, address: str, from_block: int) -> list[dict]:
    """
    Query Etherscan-like API for Upgraded() events on a proxy contract.
    Returns list of events with block, tx hash, new implementation address.
    """
    config = CHAIN_APIS.get(chain)
    if not config:
        return []

    api_key = _get_api_key(chain)
    params = {
        "module": "logs",
        "action": "getLogs",
        "address": address,
        "topic0": UPGRADED_TOPIC,
        "fromBlock": str(from_block),
        "toBlock": "latest",
        "sort": "asc",
    }
    if api_key:
        params["apikey"] = api_key

    try:
        resp = requests.get(config["url"], params=params, timeout=15)
        data = resp.json()

        if data.get("status") != "1":
            # status "0" with message "No records found" is normal
            msg = data.get("message", "")
            if "No records" in msg or "No logs" in msg:
                return []
            # Rate limit or error
            if "rate" in msg.lower() or "limit" in msg.lower():
                print(f"  [OnChain] ⏳ Rate limited on {chain}, will retry next scan")
                return []
            return []

        events = []
        for log in data.get("result", []):
            # The new implementation address is in topics[1] (indexed param)
            topics = log.get("topics", [])
            new_impl = ""
            if len(topics) > 1:
                # Address is right-padded in 32-byte topic, extract last 20 bytes
                raw = topics[1]
                new_impl = "0x" + raw[-40:]

            block_hex = log.get("blockNumber", "0x0")
            block_num = int(block_hex, 16) if isinstance(block_hex, str) else block_hex

            tx_hash = log.get("transactionHash", "")
            timestamp_hex = log.get("timeStamp", "0x0")
            try:
                timestamp = int(timestamp_hex, 16) if isinstance(timestamp_hex, str) else timestamp_hex
                event_time = datetime.fromtimestamp(timestamp, timezone.utc).isoformat()
            except Exception:
                event_time = datetime.now(timezone.utc).isoformat()

            events.append({
                "chain": chain,
                "address": address,
                "new_implementation": new_impl,
                "block": block_num,
                "tx_hash": tx_hash,
                "timestamp": event_time,
                "explorer_url": f"{config['explorer']}/tx/{tx_hash}",
            })

        return events

    except Exception as e:
        print(f"  [OnChain] ❌ Failed to query {chain} for {address[:10]}...: {e}")
        return []


def scan_upgrades(watchlist: list[dict], db_module=None) -> dict:
    """
    Main entry point: scan all watchlist projects for on-chain upgrades.

    Each watchlist item can have a `proxy_contracts` field (JSON string):
    {
        "ethereum": ["0xabc...", "0xdef..."],
        "arbitrum": ["0x123..."],
        ...
    }

    Returns summary dict with counts and details.
    """
    print("\n" + "=" * 60)
    print("🔗 On-Chain Upgrade Monitor")
    print("=" * 60)

    state = _load_state()
    all_events = []
    projects_scanned = 0
    contracts_scanned = 0
    errors = 0

    for project in watchlist:
        name = project.get("name", "Unknown")
        proxy_json = project.get("proxy_contracts", "{}")

        # Parse proxy_contracts JSON
        try:
            if isinstance(proxy_json, str):
                proxies = json.loads(proxy_json) if proxy_json else {}
            else:
                proxies = proxy_json or {}
        except json.JSONDecodeError:
            proxies = {}

        if not proxies:
            continue

        projects_scanned += 1
        print(f"\n  📦 {name}")

        for chain, addresses in proxies.items():
            if chain not in CHAIN_APIS:
                print(f"    ⚠️  Unsupported chain: {chain}")
                continue

            if isinstance(addresses, str):
                addresses = [addresses]

            for address in addresses:
                address = address.strip().lower()
                if not address:
                    continue

                contracts_scanned += 1
                state_key = f"{chain}:{address}"

                # Get from_block: either last scanned or lookback ~30 days
                from_block = state.get(state_key, 0)
                if from_block == 0:
                    # First scan: look back ~200k blocks (~30 days on Ethereum)
                    latest = _get_latest_block(chain)
                    if latest:
                        from_block = max(0, latest - 200_000)
                    else:
                        errors += 1
                        continue

                events = _get_upgrade_events(chain, address, from_block)

                if events:
                    for event in events:
                        event["project_name"] = name
                        event["project_data"] = project
                        print(f"    🚨 UPGRADE on {chain}: impl → {event['new_implementation'][:16]}...")
                        print(f"       Block: {event['block']} | TX: {event['tx_hash'][:16]}...")

                    all_events.extend(events)

                    # Update state to latest block seen
                    max_block = max(e["block"] for e in events)
                    state[state_key] = max_block + 1
                else:
                    # Update to latest block even if no events
                    latest = _get_latest_block(chain)
                    if latest:
                        state[state_key] = latest

                # Rate limit: 200ms between calls to stay under 5/sec
                time.sleep(0.2)

    _save_state(state)

    # Create Group B leads from detected upgrades
    leads_created = 0
    if all_events and db_module:
        leads_created = _create_upgrade_leads(all_events, db_module)

    summary = {
        "projects_scanned": projects_scanned,
        "contracts_scanned": contracts_scanned,
        "upgrades_detected": len(all_events),
        "leads_created": leads_created,
        "errors": errors,
        "events": all_events,
    }

    print(f"\n  {'='*50}")
    print(f"  📊 On-Chain Scan Summary")
    print(f"    Projects: {projects_scanned} | Contracts: {contracts_scanned}")
    print(f"    Upgrades: {len(all_events)} | Leads: {leads_created}")

    return summary


def _create_upgrade_leads(events: list[dict], db_module) -> int:
    """Create Group B leads from on-chain upgrade events."""
    created = 0

    try:
        existing_names = set(db_module.get_lead_names())
    except Exception:
        existing_names = set()

    # Group events by project to avoid duplicate leads
    projects_seen = set()

    for event in events:
        project_name = event.get("project_name", "Unknown")
        if project_name in existing_names or project_name in projects_seen:
            continue
        projects_seen.add(project_name)

        chain = event.get("chain", "unknown")
        new_impl = event.get("new_implementation", "???")
        explorer_url = event.get("explorer_url", "")

        lead_data = {
            "name": f"{project_name} — On-chain Upgrade ({chain})",
            "category": event.get("project_data", {}).get("category", "DeFi"),
            "score": 70,  # On-chain upgrades = high signal
            "priority": "HOT",
            "source": "onchain_monitor",
            "trigger_info": f"🔗 Proxy upgraded on {chain}. New impl: {new_impl[:16]}...",
            "stage": "Discovered",
            "summary": (
                f"🔗 On-chain proxy upgrade detected on {chain}.\n"
                f"Contract: {event.get('address', '???')}\n"
                f"New implementation: {new_impl}\n"
                f"Block: {event.get('block', '???')}\n"
                f"TX: {explorer_url}\n"
                f"Time: {event.get('timestamp', '???')}\n\n"
                f"This is a high-signal lead — the project just deployed new code "
                f"that needs security review."
            ),
            "pitch_services": "Smart Contract Audit (upgrade delta), Formal Verification",
            "score_breakdown": json.dumps({
                "onchain_upgrade": 40,
                "proxy_pattern": 15,
                "audit_timing": 15,
                "label": "On-chain upgrade detected"
            }),
            "scored_by": "onchain_monitor",
            "lead_group": "B",
            "github_url": event.get("project_data", {}).get("github_repo", ""),
            "twitter_url": event.get("project_data", {}).get("x_account", ""),
        }

        try:
            db_module.insert_lead(lead_data)
            created += 1
            print(f"    ✅ Lead created: {lead_data['name']}")
        except Exception as e:
            print(f"    ❌ Failed to create lead for {project_name}: {e}")

    return created


if __name__ == "__main__":
    # Test mode: scan with a local watchlist example
    test_watchlist = [
        {
            "name": "Test USDC Proxy",
            "category": "Stablecoin",
            "proxy_contracts": json.dumps({
                "ethereum": ["0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"]
            }),
        }
    ]
    result = scan_upgrades(test_watchlist)
    print(f"\nResult: {json.dumps(result, indent=2, default=str)}")
