"""
Verichains LeadHunter — Audit Checker Module
Multi-source audit detection for DeFi protocols.

Sources checked (in order):
1. DeFiLlama data (audits + audit_links fields)
2. GitHub repository audit folders (/audits, /audit, /security)
3. GitHub org — search ALL repos for audit folders
4. Protocol website security pages (/security, /audits, /*-audit.pdf)
5. Docs site audit pages (docs.{domain}/security/audits etc.)
"""

import re
import time
import requests
import config

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

def _gh_headers():
    headers = {"Accept": "application/vnd.github.v3+json"}
    if config.GITHUB_TOKEN:
        headers["Authorization"] = f"token {config.GITHUB_TOKEN}"
    return headers


def _extract_auditor(text: str) -> str:
    """Try to extract a known auditor name from text."""
    text_lower = text.lower()
    for auditor in _KNOWN_AUDITORS:
        if auditor in text_lower:
            return auditor.replace("_", " ").title()
    return ""


# ================================================================
#  GitHub Audit Folder Check (single repo)
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
    """
    Check GitHub for audit folders/files.
    Handles both org-only URLs and org/repo URLs.
    For orgs: checks ALL repos for audit folders.
    """
    if not github_url:
        return {"found": False}

    headers = _gh_headers()

    # Parse GitHub URL
    # Match org/repo pattern
    repo_match = re.search(r"github\.com/([^/]+/[^/]+)", github_url)
    org_match = re.search(r"github\.com/([^/]+)$", github_url)

    if repo_match:
        # Direct repo — check audit folders
        repo_path = repo_match.group(1).rstrip("/")
        result = _check_repo_audit_folders(repo_path, headers)
        if result.get("found"):
            return result
        # Also fall through to check org's other repos
        org_name = repo_path.split("/")[0]
    elif org_match:
        org_name = org_match.group(1).rstrip("/")
    else:
        return {"found": False}

    # Check ALL repos in the org for audit folders (up to 30 repos)
    try:
        url = f"https://api.github.com/orgs/{org_name}/repos?per_page=30&sort=updated"
        resp = requests.get(url, headers=headers, timeout=8)
        if resp.status_code == 200:
            repos = resp.json()
            for r in repos:
                rname = r.get("full_name", "")
                repo_result = _check_repo_audit_folders(rname, headers)
                if repo_result.get("found"):
                    return repo_result
                time.sleep(0.1)  # Rate limit
    except Exception:
        pass

    # Check user repos if org lookup failed
    try:
        url = f"https://api.github.com/users/{org_name}/repos?per_page=30&sort=updated"
        resp = requests.get(url, headers=headers, timeout=8)
        if resp.status_code == 200:
            repos = resp.json()
            for r in repos:
                rname = r.get("full_name", "")
                repo_result = _check_repo_audit_folders(rname, headers)
                if repo_result.get("found"):
                    return repo_result
                time.sleep(0.1)
    except Exception:
        pass

    return {"found": False}


# ================================================================
#  Protocol Website Audit Page Check
# ================================================================

def _check_website_audits(website_url: str) -> dict:
    """
    Check protocol website for security/audit pages.
    Also checks for audit PDF files linked from the site.
    """
    if not website_url:
        return {"found": False}

    website_url = website_url.rstrip("/")

    # Common audit page paths
    paths = ["/security", "/audits", "/audit",
             "/docs/security", "/docs/audits",
             "/security/audits"]

    ua = {"User-Agent": "LeadHunter/1.0"}

    for path in paths:
        try:
            url = website_url + path
            resp = requests.get(url, timeout=8, allow_redirects=True, headers=ua)
            if resp.status_code == 200:
                text = resp.text.lower()
                if "audit" in text and ("report" in text or "security" in text or ".pdf" in text):
                    found_auditor = _extract_auditor(text)
                    return {
                        "found": True,
                        "source": f"Website ({path})",
                        "auditor": found_auditor or "See page",
                        "links": [url],
                    }
        except Exception:
            pass

    # Check homepage for audit links (PDF links, audit mentions)
    try:
        resp = requests.get(website_url, timeout=8, allow_redirects=True, headers=ua)
        if resp.status_code == 200:
            text = resp.text.lower()
            # Look for audit PDF links on main page
            pdf_links = re.findall(r'href=["\']([^"\']*audit[^"\']*\.pdf)', text, re.IGNORECASE)
            if pdf_links:
                link = pdf_links[0]
                if not link.startswith("http"):
                    link = website_url + "/" + link.lstrip("/")
                found_auditor = _extract_auditor(link)
                return {
                    "found": True,
                    "source": "Website (PDF link)",
                    "auditor": found_auditor or "See report",
                    "links": [link],
                }
    except Exception:
        pass

    return {"found": False}


# ================================================================
#  Docs Site Audit Page Check
# ================================================================

def _check_docs_audits(website_url: str, name: str) -> dict:
    """
    Check common docs sites for audit pages.
    Many protocols have docs on separate domains.
    """
    if not website_url:
        return {"found": False}

    domain_match = re.search(r"https?://(?:www\.|app\.)?([^/]+)", website_url)
    if not domain_match:
        return {"found": False}

    domain = domain_match.group(1)
    parts = domain.split(".")

    # Build list of docs URLs to check
    docs_urls = set()
    if len(parts) >= 2:
        base = parts[0]
        tld = ".".join(parts[1:])
        docs_urls.update([
            f"https://docs.{domain}",
            f"https://docs.{base}.finance",
            f"https://docs.{base}.io",
            f"https://docs.{base}.xyz",
            f"https://docs.{base}dao.finance",
            f"https://{base}.gitbook.io",
        ])

    # Also try name-based docs URL
    slug = name.lower().replace(" ", "").replace(".", "")
    docs_urls.update([
        f"https://docs.{slug}.finance",
        f"https://docs.{slug}dao.finance",
        f"https://docs.{slug}.io",
    ])

    ua = {"User-Agent": "LeadHunter/1.0"}
    paths = ["/security/audits", "/main/security/audits",
             "/security", "/main/security",
             "/audits", "/audit"]

    for docs_base in docs_urls:
        for path in paths:
            try:
                url = docs_base + path
                resp = requests.get(url, timeout=6, allow_redirects=True, headers=ua)
                if resp.status_code == 200:
                    text = resp.text.lower()
                    if "audit" in text and ("report" in text or ".pdf" in text):
                        found_auditor = _extract_auditor(text)
                        return {
                            "found": True,
                            "source": f"Docs ({url})",
                            "auditor": found_auditor or "See page",
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

    Returns:
        {
            "has_audit": bool,
            "audit_status": str,
            "audit_source": str,
            "audit_links": list[str],
        }
    """
    name = protocol.get("name") or "Unknown"
    audits = protocol.get("audits") or "0"
    audit_links = protocol.get("audit_links") or []
    github_raw = protocol.get("github") or []
    website = protocol.get("url") or ""

    # Build GitHub URL
    if isinstance(github_raw, list) and github_raw:
        github_url = github_raw[0]
        if not github_url.startswith("http"):
            github_url = f"https://github.com/{github_url}"
    elif isinstance(github_raw, str) and github_raw:
        github_url = github_raw if github_raw.startswith("http") else f"https://github.com/{github_raw}"
    else:
        github_url = ""

    # Source 1: DeFiLlama data
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

    # Source 2: GitHub audit folders (checks all org repos)
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

    # Source 3: Protocol website
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
    print("❌", end=" ", flush=True)

    # Source 4: Docs site
    print(f"Docs...", end=" ", flush=True)
    docs_result = _check_docs_audits(website, name)
    if docs_result.get("found"):
        links = docs_result.get("links", [])
        auditor = docs_result.get("auditor", "")
        print(f"✅ {auditor}")
        return {
            "has_audit": True,
            "audit_status": f"✅ Audited by {auditor} — {', '.join(links[:2])}",
            "audit_source": "Docs",
            "audit_links": links,
        }
    print("❌")

    return {
        "has_audit": False,
        "audit_status": "❌ No audit found (checked DeFiLlama, GitHub, website, docs)",
        "audit_source": "none",
        "audit_links": [],
    }
