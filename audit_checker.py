"""
Verichains LeadHunter — Audit Checker Module
Multi-source audit detection for DeFi protocols.

Audit Check Pipeline:
1. DeFiLlama data (audits + audit_links fields)
2. GitHub repository audit folders (LOCAL only — skipped on Vercel)
3. Google search for audit reports (works everywhere)
4. Protocol website + homepage PDF scan (fallback)
"""

import re
import time
import urllib.parse
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
                break
        except Exception:
            pass

    return {"found": False}


# ================================================================
#  Google Search Audit Check
# ================================================================

def _search_audit_google(name: str) -> dict:
    """
    Search Google for audit reports.
    Parses result URLs and checks for known auditor names.
    """
    queries = [
        f'"{name}" audit report',
        f'"{name}" smart contract audit',
    ]

    ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    for query in queries:
        try:
            resp = requests.get(
                "https://www.google.com/search",
                params={"q": query, "num": 5},
                headers={"User-Agent": ua},
                timeout=10,
            )
            if resp.status_code != 200:
                continue

            text = resp.text.lower()

            # Extract URLs from Google results
            raw_urls = re.findall(r'/url\?q=(https?://[^&"]+)', resp.text)
            urls = [urllib.parse.unquote(u) for u in raw_urls
                    if "google" not in u and "youtube" not in u]

            # Check for known auditors in page text
            auditor = _extract_auditor(text)

            if auditor:
                # Find a URL related to the auditor
                best_link = ""
                auditor_key = auditor.lower().split()[0]
                for u in urls:
                    if auditor_key in u.lower() or "audit" in u.lower():
                        best_link = u
                        break
                if not best_link and urls:
                    best_link = urls[0]

                return {
                    "found": True,
                    "source": "Google Search",
                    "auditor": auditor,
                    "links": [best_link] if best_link else [],
                }

            # Check for audit PDF links
            pdf_urls = [u for u in urls if "audit" in u.lower() and u.endswith(".pdf")]
            if pdf_urls:
                return {
                    "found": True,
                    "source": "Google Search",
                    "auditor": _extract_auditor(pdf_urls[0]) or "See report",
                    "links": pdf_urls[:2],
                }

            time.sleep(1)  # Rate limit between queries
        except Exception:
            pass

    return {"found": False}


# ================================================================
#  Website Fallback Check
# ================================================================

def _check_website_audits(website_url: str) -> dict:
    """Check protocol website homepage for audit PDF links."""
    if not website_url:
        return {"found": False}

    website_url = website_url.rstrip("/")
    ua = {"User-Agent": "LeadHunter/1.0"}

    # Check homepage for audit PDF links
    try:
        resp = requests.get(website_url, timeout=8, allow_redirects=True, headers=ua)
        if resp.status_code == 200:
            text = resp.text.lower()
            pdf_links = re.findall(r'href=["\']([^"\']*audit[^"\']*\.pdf)', text, re.IGNORECASE)
            if pdf_links:
                link = pdf_links[0]
                if not link.startswith("http"):
                    link = website_url + "/" + link.lstrip("/")
                return {
                    "found": True,
                    "source": "Website (PDF)",
                    "auditor": _extract_auditor(link) or "See report",
                    "links": [link],
                }
    except Exception:
        pass

    # Check common audit page paths
    for path in ["/security", "/audits", "/audit"]:
        try:
            url = website_url + path
            resp = requests.get(url, timeout=6, allow_redirects=True, headers=ua)
            if resp.status_code == 200:
                text = resp.text.lower()
                if "audit" in text and ("report" in text or ".pdf" in text):
                    found_auditor = _extract_auditor(text)
                    if found_auditor:
                        return {
                            "found": True,
                            "source": f"Website ({path})",
                            "auditor": found_auditor,
                            "links": [url],
                        }
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
    3. Google search
    4. Website homepage PDF check (fallback)
    """
    name = protocol.get("name") or "Unknown"
    audits = protocol.get("audits") or "0"
    audit_links = protocol.get("audit_links") or []
    github_raw = protocol.get("github") or []
    website = protocol.get("url") or ""

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

    # ── Source 3: Google search ──
    print(f"  [Audit] 🔍 {name}: Google...", end=" ", flush=True)
    search_result = _search_audit_google(name)
    if search_result.get("found"):
        links = search_result.get("links", [])
        auditor = search_result.get("auditor", "")
        print(f"✅ {auditor}")
        return {
            "has_audit": True,
            "audit_status": f"✅ Audited by {auditor} — found via search: {', '.join(links[:2])}",
            "audit_source": "Google",
            "audit_links": links,
        }
    print("❌", end=" ", flush=True)

    # ── Source 4: Website fallback ──
    if website:
        print(f"Website...", end=" ", flush=True)
        web_result = _check_website_audits(website)
        if web_result.get("found"):
            links = web_result.get("links", [])
            auditor = web_result.get("auditor", "")
            print(f"✅ {auditor}")
            return {
                "has_audit": True,
                "audit_status": f"✅ Audited by {auditor} — {', '.join(links[:2])}",
                "audit_source": "Website",
                "audit_links": links,
            }
        print("❌")
    else:
        print("")

    return {
        "has_audit": False,
        "audit_status": "❌ No audit found (checked DeFiLlama, GitHub, Google, website)",
        "audit_source": "none",
        "audit_links": [],
    }
