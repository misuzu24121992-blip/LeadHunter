"""
Verichains LeadHunter — Audit Checker Module
Multi-source audit detection for DeFi protocols.

Audit Check Pipeline:
1. DeFiLlama data (audits + audit_links fields)
2. GitHub repository audit folders (LOCAL only — skipped on Vercel)
3. Web search via DuckDuckGo (works on both local + Vercel)
"""

import re
import time
import requests
import config
import os

_KNOWN_AUDITORS = [
    "certik", "mixbytes", "ackee", "nethermind", "openzeppelin",
    "trail of bits", "trail_of_bits", "trailofbits",
    "sherlock", "quantstamp", "consensys", "consensys diligence",
    "halborn", "peckshield", "slowmist", "solidproof", "movebit",
    "hacken", "thesis defense", "thesis_defense",
    "spearbit", "code4rena", "zellic", "least authority",
    "chainsecurity", "cyfrin", "immunefi", "oak security",
    "csc", "ottersec", "veridise",
]


def _extract_auditor(text: str) -> str:
    """Try to extract a known auditor name from text."""
    text_lower = text.lower()
    for auditor in _KNOWN_AUDITORS:
        if auditor in text_lower:
            return auditor.replace("_", " ").title()
    return ""


def _gh_headers():
    headers = {"Accept": "application/vnd.github.v3+json"}
    if config.GITHUB_TOKEN:
        headers["Authorization"] = f"token {config.GITHUB_TOKEN}"
    return headers


# ================================================================
#  GitHub Audit Folder Check (LOCAL only)
# ================================================================

def _check_repo_audit_folders(repo_path: str, headers: dict) -> dict:
    """Check a single repo for audit folders."""
    audit_dirs = ["audits", "audit", "security", "security-audits"]
    found_links = []
    auditor = ""

    for dirname in audit_dirs:
        try:
            url = f"https://api.github.com/repos/{repo_path}/contents/{dirname}"
            resp = requests.get(url, headers=headers, timeout=8)
            if resp.status_code == 200:
                contents = resp.json()
                if isinstance(contents, list):
                    for item in contents:
                        name = (item.get("name") or "").lower()
                        if name.endswith(".pdf") or "audit" in name:
                            found_links.append(item.get("html_url", ""))
                            if not auditor:
                                auditor = _extract_auditor(name)
        except Exception:
            pass

    if found_links:
        return {
            "found": True,
            "source": "GitHub",
            "auditor": auditor or "Unknown auditor",
            "links": found_links[:3],
        }
    return {"found": False}


def _check_github_audits(github_url: str) -> dict:
    """Check GitHub org/repo for audit folders. Scans ALL repos in org."""
    if not github_url:
        return {"found": False}

    headers = _gh_headers()

    # Parse GitHub URL
    repo_match = re.search(r"github\.com/([^/]+/[^/]+)", github_url)
    org_match = re.search(r"github\.com/([^/]+)$", github_url)

    if repo_match:
        repo_path = repo_match.group(1).rstrip("/")
        result = _check_repo_audit_folders(repo_path, headers)
        if result.get("found"):
            return result
        org_name = repo_path.split("/")[0]
    elif org_match:
        org_name = org_match.group(1).rstrip("/")
    else:
        return {"found": False}

    # Scan ALL repos in org for audit folders
    for endpoint in ["orgs", "users"]:
        try:
            url = f"https://api.github.com/{endpoint}/{org_name}/repos?per_page=30&sort=updated"
            resp = requests.get(url, headers=headers, timeout=8)
            if resp.status_code == 200:
                repos = resp.json()
                for r in repos:
                    rname = r.get("full_name", "")
                    repo_result = _check_repo_audit_folders(rname, headers)
                    if repo_result.get("found"):
                        return repo_result
                    time.sleep(0.1)
                break  # Don't try "users" if "orgs" worked
        except Exception:
            pass

    return {"found": False}


# ================================================================
#  Web Search Audit Check (DuckDuckGo — works everywhere)
# ================================================================

def _search_audit_web(name: str) -> dict:
    """
    Search for audit reports via DuckDuckGo HTML.
    Queries: "{name} audit report", "{name} smart contract audit"
    """
    queries = [
        f'"{name}" audit report',
        f'"{name}" smart contract audit',
    ]

    for query in queries:
        try:
            resp = requests.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                headers={"User-Agent": "LeadHunter/1.0"},
                timeout=10,
            )
            if resp.status_code != 200:
                continue

            text = resp.text.lower()

            # Look for known auditor mentions in search results
            auditor = _extract_auditor(text)

            # Look for audit-related result links
            # DuckDuckGo HTML results have links in <a class="result__a" href="...">
            audit_links = re.findall(
                r'href="([^"]*(?:audit|security)[^"]*\.pdf)"',
                text, re.IGNORECASE
            )

            if auditor:
                # Extract a result URL with the auditor name
                link_pattern = rf'href="(https?://[^"]*{re.escape(auditor.lower().split()[0])}[^"]*)"'
                specific_links = re.findall(link_pattern, text, re.IGNORECASE)
                best_link = specific_links[0] if specific_links else (audit_links[0] if audit_links else "")

                return {
                    "found": True,
                    "source": "Web Search",
                    "auditor": auditor,
                    "links": [best_link] if best_link else [],
                }

            # Check for generic audit mentions in results
            if audit_links:
                return {
                    "found": True,
                    "source": "Web Search",
                    "auditor": "See report",
                    "links": audit_links[:2],
                }

            # Check if results mention audit + report patterns
            if "audit report" in text and name.lower() in text:
                # Extract any meaningful URL
                urls = re.findall(r'href="(https?://[^"]*audit[^"]*)"', text, re.IGNORECASE)
                if urls:
                    return {
                        "found": True,
                        "source": "Web Search",
                        "auditor": "See search results",
                        "links": urls[:2],
                    }

            time.sleep(0.5)  # Rate limit between queries
        except Exception:
            pass

    return {"found": False}


# ================================================================
#  Main Audit Check Pipeline
# ================================================================

def check_audit(protocol: dict) -> dict:
    """
    Run multi-source audit check for a protocol.

    Pipeline:
    1. DeFiLlama data
    2. GitHub audit folders (LOCAL only, skipped on Vercel)
    3. Web search (DuckDuckGo — works everywhere)
    """
    name = protocol.get("name") or "Unknown"
    audits = protocol.get("audits") or "0"
    audit_links = protocol.get("audit_links") or []
    github_raw = protocol.get("github") or []

    is_vercel = bool(os.environ.get("VERCEL") or os.environ.get("VERCEL_URL"))

    # Build GitHub URL
    if isinstance(github_raw, list) and github_raw:
        github_url = github_raw[0]
        if not github_url.startswith("http"):
            github_url = f"https://github.com/{github_url}"
    elif isinstance(github_raw, str) and github_raw:
        github_url = github_raw if github_raw.startswith("http") else f"https://github.com/{github_raw}"
    else:
        github_url = ""

    # ── Source 1: DeFiLlama data ──
    if audits != "0" and audit_links:
        return {
            "has_audit": True,
            "audit_status": f"✅ Audited — {len(audit_links)} report(s): {', '.join(audit_links[:2])}",
            "audit_source": "DeFiLlama",
            "audit_links": audit_links,
        }
    elif audits != "0":
        return {
            "has_audit": True,
            "audit_status": "✅ DeFiLlama reports audit exists",
            "audit_source": "DeFiLlama",
            "audit_links": [],
        }

    # ── Source 2: GitHub audit folders (LOCAL only) ──
    if not is_vercel and github_url:
        print(f"  [Audit] 🔍 {name}: GitHub...", end=" ", flush=True)
        gh_result = _check_github_audits(github_url)
        if gh_result.get("found"):
            links = gh_result.get("links", [])
            auditor = gh_result.get("auditor", "")
            print(f"✅ {auditor}")
            return {
                "has_audit": True,
                "audit_status": f"✅ Audited by {auditor} — GitHub: {', '.join(links[:2])}",
                "audit_source": "GitHub",
                "audit_links": links,
            }
        print("❌", end=" ", flush=True)

    # ── Source 3: Web search (works on both local + Vercel) ──
    print(f"  [Audit] 🔍 {name}: Web search...", end=" ", flush=True)
    search_result = _search_audit_web(name)
    if search_result.get("found"):
        links = search_result.get("links", [])
        auditor = search_result.get("auditor", "")
        print(f"✅ {auditor}")
        return {
            "has_audit": True,
            "audit_status": f"✅ Audited by {auditor} — Web: {', '.join(links[:2])}",
            "audit_source": "Web Search",
            "audit_links": links,
        }
    print("❌")

    return {
        "has_audit": False,
        "audit_status": "❌ No audit found (checked DeFiLlama, GitHub, web search)",
        "audit_source": "none",
        "audit_links": [],
    }
