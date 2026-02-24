"""
Verichains LeadHunter — Audit Checker Module
Multi-source audit detection for DeFi protocols.

Audit Check Pipeline:
1. DeFiLlama data (audits + audit_links fields)
2. GitHub repository audit folders (LOCAL only — skipped on Vercel)
3. DuckDuckGo Lite search (works everywhere, no CAPTCHA)
4. Protocol website + homepage PDF scan (fallback)
"""

import re
import time
import urllib.parse
import requests
import config
import os

_KNOWN_AUDITORS = [
    # Longer/more specific names first
    "trail of bits", "trail_of_bits", "trailofbits",
    "cairo security clan",
    "consensys diligence", "thesis defense", "thesis_defense",
    "least authority", "oak security",
    "ackee blockchain",
    "openzeppelin", "chainsecurity",
    "certik", "mixbytes", "nethermind",
    "sherlock", "quantstamp", "consensys",
    "halborn", "peckshield", "slowmist", "solidproof", "movebit",
    "hacken", "spearbit", "code4rena", "zellic",
    "cyfrin", "immunefi", "ottersec", "veridise",
    "electisec", "scauditstudio",
    "ackee",
]

# Domains/patterns that indicate an audit URL
_AUDIT_URL_PATTERNS = [
    "trustblock.run/audit",
    "sherlock-audit",
    "audit_report",
    "audit-report",
    "audits_public",
    "/audits/",
    "/audit/",
    "/security-audit",
]


def _extract_auditor(text: str) -> str:
    """Try to extract a known auditor name from text using word boundaries."""
    text_lower = text.lower()
    for auditor in _KNOWN_AUDITORS:
        pattern = r'\b' + re.escape(auditor) + r'\b'
        if re.search(pattern, text_lower):
            return auditor.replace("_", " ").title()
    return ""


def _is_audit_url(url: str) -> bool:
    """Check if a URL looks like an audit report link."""
    url_lower = url.lower()
    for pattern in _AUDIT_URL_PATTERNS:
        if pattern in url_lower:
            return True
    if url_lower.endswith(".pdf") and "audit" in url_lower:
        return True
    return False


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
    """Check GitHub org/repo for audit folders."""
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

    # Scan repos in org for audit folders
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
#  DuckDuckGo Lite Search (replaces broken Google search)
# ================================================================

def _search_ddg_lite(query: str) -> list:
    """
    Search using DuckDuckGo Lite — returns actual results with URLs.
    Unlike Google and DDG HTML, DDG Lite does NOT block automated requests.
    Returns list of {url, title, snippet} dicts.
    """
    try:
        resp = requests.get(
            "https://lite.duckduckgo.com/lite/",
            params={"q": query},
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"},
            timeout=10,
        )
        if resp.status_code != 200:
            return []

        results = []

        # DDG Lite format: <a rel="nofollow" href="//duckduckgo.com/l/?uddg=ENCODED_URL" class='result-link'>title</a>
        link_matches = re.findall(
            r'<a\s+rel="nofollow"\s+href="//duckduckgo\.com/l/\?uddg=(https?[^&"]+)[^"]*"\s+class=\'result-link\'>(.*?)</a>',
            resp.text, re.DOTALL)

        # Snippets follow links
        snippets = re.findall(r"class='result-snippet'>\s*(.*?)\s*</td>", resp.text, re.DOTALL)

        for i, (encoded_url, raw_title) in enumerate(link_matches):
            url = urllib.parse.unquote(encoded_url)
            title = re.sub(r'<[^>]+>', '', raw_title).strip()
            snippet = re.sub(r'<[^>]+>', '', snippets[i]).strip() if i < len(snippets) else ""
            results.append({"url": url, "title": title, "snippet": snippet})

        return results
    except Exception:
        return []


def _search_audit_web(name: str) -> dict:
    """
    Search for audit reports using DuckDuckGo Lite.
    Checks result titles, snippets, and URLs for known auditors and audit patterns.
    """
    queries = [
        f'"{name}" audit report',
        f'"{name}" smart contract audit',
    ]

    for query in queries:
        results = _search_ddg_lite(query)

        if not results:
            time.sleep(0.5)
            continue

        # Combine all text from results for auditor matching
        all_text = " ".join(
            f"{r['title']} {r['snippet']} {r['url']}" for r in results
        )

        # Check for known auditors in combined text
        auditor = _extract_auditor(all_text)

        # Check for audit URLs in results
        audit_urls = [r["url"] for r in results if _is_audit_url(r["url"])]

        # Check for PDF audit links
        pdf_urls = [r["url"] for r in results
                    if r["url"].lower().endswith(".pdf") and "audit" in r["url"].lower()]

        # If we found an auditor name, report it
        if auditor:
            best_link = ""
            auditor_key = auditor.lower().split()[0]
            for r in results:
                if auditor_key in r["url"].lower() or _is_audit_url(r["url"]):
                    best_link = r["url"]
                    break
            if not best_link and audit_urls:
                best_link = audit_urls[0]
            if not best_link and results:
                best_link = results[0]["url"]

            return {
                "found": True,
                "source": "Web Search",
                "auditor": auditor,
                "links": [best_link] if best_link else [],
            }

        # If we found audit URLs but no named auditor
        if audit_urls:
            # Try to extract auditor from the URL or page title
            for au in audit_urls:
                a = _extract_auditor(au)
                if a:
                    auditor = a
                    break
            return {
                "found": True,
                "source": "Web Search",
                "auditor": auditor or "See report",
                "links": audit_urls[:2],
            }

        # If we found audit PDFs
        if pdf_urls:
            for pu in pdf_urls:
                a = _extract_auditor(pu)
                if a:
                    auditor = a
                    break
            return {
                "found": True,
                "source": "Web Search",
                "auditor": auditor or "See report",
                "links": pdf_urls[:2],
            }

        # Check snippets for audit mentions with links
        for r in results:
            snippet_lower = r["snippet"].lower()
            title_lower = r["title"].lower()
            if ("audit" in title_lower and ("report" in title_lower or "review" in title_lower or "security" in title_lower)):
                a = _extract_auditor(r["snippet"] + " " + r["title"])
                return {
                    "found": True,
                    "source": "Web Search",
                    "auditor": a or "See report",
                    "links": [r["url"]],
                }

        time.sleep(0.5)

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
    3. DuckDuckGo Lite search (works everywhere)
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

    # ── Source 3: DuckDuckGo Lite search ──
    print(f"  [Audit] 🔍 {name}: DDG search...", end=" ", flush=True)
    search_result = _search_audit_web(name)
    if search_result.get("found"):
        links = search_result.get("links", [])
        auditor = search_result.get("auditor", "")
        print(f"✅ {auditor}")
        return {
            "has_audit": True,
            "audit_status": f"✅ Audited by {auditor} — {', '.join(links[:2])}",
            "audit_source": "Web Search",
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
        "audit_status": "❌ No audit found (checked DeFiLlama, GitHub, web search, website)",
        "audit_source": "none",
        "audit_links": [],
    }
