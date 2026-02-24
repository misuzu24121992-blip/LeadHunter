"""
Verichains LeadHunter — Audit Checker Module
Multi-source audit detection for DeFi protocols.

Audit Check Pipeline:
1. DeFiLlama data (audits + audit_links fields)
2. GitHub audit folders + README scan (LOCAL only — skipped on Vercel)
3. DuckDuckGo Lite search (rate-limited but works with backoff)
4. Protocol website + homepage PDF scan (fallback)
"""

import re
import time
import random
import urllib.parse
import base64
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

_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
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
#  GitHub Audit Folder + README Check (LOCAL only)
# ================================================================

def _check_repo_audit_folders(repo_path: str, headers: dict) -> dict:
    """Check a single repo for audit folders."""
    audit_dirs = ["audits", "audit", "security", "security-audits"]
    found_links = []
    auditor = ""

    # First: check ROOT of repo for audit PDFs
    try:
        url = f"https://api.github.com/repos/{repo_path}/contents/"
        resp = requests.get(url, headers=headers, timeout=8)
        if resp.status_code == 200:
            contents = resp.json()
            if isinstance(contents, list):
                for item in contents:
                    name = (item.get("name") or "").lower()
                    if name.endswith(".pdf") and "audit" in name:
                        found_links.append(item.get("html_url", ""))
                        if not auditor:
                            auditor = _extract_auditor(name)
    except Exception:
        pass

    # Then: check audit subdirectories
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


def _check_repo_readme(repo_path: str, headers: dict) -> dict:
    """Check a repo's README for audit mentions."""
    try:
        url = f"https://api.github.com/repos/{repo_path}/readme"
        resp = requests.get(url, headers=headers, timeout=8)
        if resp.status_code != 200:
            return {"found": False}

        content = base64.b64decode(resp.json().get("content", "")).decode("utf-8", errors="ignore")
        content_lower = content.lower()

        if "audit" not in content_lower:
            return {"found": False}

        # Extract auditor name from README text
        auditor = _extract_auditor(content)

        # Extract links near audit mentions
        audit_links = []
        # Find markdown links near "audit" keyword
        for match in re.finditer(r'audit', content_lower):
            start = max(0, match.start() - 200)
            end = min(len(content), match.end() + 200)
            context = content[start:end]
            links = re.findall(r'\[([^\]]*)\]\((https?://[^)]+)\)', context)
            for link_text, link_url in links:
                if "audit" in link_text.lower() or "audit" in link_url.lower():
                    audit_links.append(link_url)
            # Also check for bare URLs
            bare_urls = re.findall(r'(https?://\S+)', context)
            for u in bare_urls:
                if "audit" in u.lower() or _is_audit_url(u):
                    audit_links.append(u.rstrip(").,"))

        if auditor or audit_links:
            return {
                "found": True,
                "source": "GitHub README",
                "auditor": auditor or "See README",
                "links": list(set(audit_links))[:3],
            }

    except Exception:
        pass
    return {"found": False}


def _check_github_audits(github_url: str) -> dict:
    """Check GitHub org/repo for audit folders and README mentions."""
    if not github_url:
        return {"found": False}

    headers = _gh_headers()

    repo_match = re.search(r"github\.com/([^/]+/[^/]+)", github_url)
    org_match = re.search(r"github\.com/([^/]+)$", github_url)

    if repo_match:
        repo_path = repo_match.group(1).rstrip("/")
        # Check audit folders
        result = _check_repo_audit_folders(repo_path, headers)
        if result.get("found"):
            return result
        # Check README
        readme_result = _check_repo_readme(repo_path, headers)
        if readme_result.get("found"):
            return readme_result
        org_name = repo_path.split("/")[0]
    elif org_match:
        org_name = org_match.group(1).rstrip("/")
    else:
        return {"found": False}

    # Scan ONLY the most relevant repos in org (max 3 total checks)
    for endpoint in ["orgs", "users"]:
        try:
            url = f"https://api.github.com/{endpoint}/{org_name}/repos?per_page=30&sort=updated"
            resp = requests.get(url, headers=headers, timeout=8)
            if resp.status_code == 200:
                repos = resp.json()
                # Prioritize: audit/security repos first, then readme/docs
                priority_repos = []
                secondary_repos = []
                for r in repos:
                    rname_lower = r.get("name", "").lower()
                    if "audit" in rname_lower or "security" in rname_lower:
                        priority_repos.append(r)
                    elif any(kw in rname_lower for kw in ["readme", "docs", "doc"]):
                        secondary_repos.append(r)

                # Check max 3 repos total
                check_count = 0
                for r in (priority_repos + secondary_repos)[:3]:
                    rname = r.get("full_name", "")
                    folder_result = _check_repo_audit_folders(rname, headers)
                    if folder_result.get("found"):
                        return folder_result
                    readme_result = _check_repo_readme(rname, headers)
                    if readme_result.get("found"):
                        return readme_result
                    check_count += 1
                break
        except Exception:
            pass

    return {"found": False}


# ================================================================
#  DuckDuckGo Lite Search
# ================================================================

def _search_ddg_lite(query: str) -> list:
    """
    Search using DuckDuckGo Lite.
    Uses random UA and accepts both GET/POST to avoid CAPTCHA.
    """
    ua = random.choice(_USER_AGENTS)

    for method in ["GET", "POST"]:
        try:
            if method == "GET":
                resp = requests.get(
                    "https://lite.duckduckgo.com/lite/",
                    params={"q": query},
                    headers={"User-Agent": ua, "Accept": "text/html", "Accept-Language": "en-US,en;q=0.5"},
                    timeout=10,
                )
            else:
                resp = requests.post(
                    "https://lite.duckduckgo.com/lite/",
                    data={"q": query},
                    headers={"User-Agent": ua, "Accept": "text/html", "Accept-Language": "en-US,en;q=0.5"},
                    timeout=10,
                )

            if resp.status_code not in (200, 202) or 'result-link' not in resp.text:
                continue

            results = []
            link_matches = re.findall(
                r'<a\s+rel="nofollow"\s+href="//duckduckgo\.com/l/\?uddg=(https?[^&"]+)[^"]*"\s+class=\'result-link\'>(.*?)</a>',
                resp.text, re.DOTALL)

            snippets = re.findall(r"class='result-snippet'>\s*(.*?)\s*</td>", resp.text, re.DOTALL)

            for i, (encoded_url, raw_title) in enumerate(link_matches):
                url = urllib.parse.unquote(encoded_url)
                title = re.sub(r'<[^>]+>', '', raw_title).strip()
                snippet = re.sub(r'<[^>]+>', '', snippets[i]).strip() if i < len(snippets) else ""
                results.append({"url": url, "title": title, "snippet": snippet})

            if results:
                return results
        except Exception:
            pass

    return []


def _search_audit_web(name: str) -> dict:
    """
    Search for audit reports using DuckDuckGo Lite.
    Skipped on Vercel (rate-limited from serverless IPs).
    """
    is_vercel = bool(os.environ.get("VERCEL") or os.environ.get("VERCEL_URL"))
    if is_vercel:
        return {"found": False}

    queries = [
        f'"{name}" audit report',
    ]

    for query in queries:
        results = _search_ddg_lite(query)

        if not results:
            time.sleep(1)
            continue

        # Combine all text from results
        all_text = " ".join(
            f"{r['title']} {r['snippet']} {r['url']}" for r in results
        )

        auditor = _extract_auditor(all_text)
        audit_urls = [r["url"] for r in results if _is_audit_url(r["url"])]
        pdf_urls = [r["url"] for r in results
                    if r["url"].lower().endswith(".pdf") and "audit" in r["url"].lower()]

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

        if audit_urls:
            auditor = ""
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

        if pdf_urls:
            auditor = ""
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

        # Check titles for audit-related keywords
        for r in results:
            title_lower = r["title"].lower()
            if ("audit" in title_lower and ("report" in title_lower or "review" in title_lower or "security" in title_lower)):
                a = _extract_auditor(r["snippet"] + " " + r["title"])
                return {
                    "found": True,
                    "source": "Web Search",
                    "auditor": a or "See report",
                    "links": [r["url"]],
                }

        time.sleep(1)

    return {"found": False}


# ================================================================
#  Website Fallback Check
# ================================================================

def _check_website_audits(website_url: str) -> dict:
    """Check protocol website for audit PDF links."""
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
    2. GitHub audit folders + README (LOCAL only, skipped on Vercel)
    3. DuckDuckGo Lite search (works with rate limiting)
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

    # ── Source 2: GitHub audit folders + README (LOCAL only) ──
    if not is_vercel and github_url:
        print(f"  [Audit] 🔍 {name}: GitHub...", end=" ", flush=True)
        gh_result = _check_github_audits(github_url)
        if gh_result.get("found"):
            links = gh_result.get("links", [])
            auditor = gh_result.get("auditor", "")
            src = gh_result.get("source", "GitHub")
            print(f"✅ {auditor} ({src})")
            return {
                "has_audit": True,
                "audit_status": f"✅ Audited by {auditor} — {src}: {', '.join(links[:2])}",
                "audit_source": src,
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
        "audit_status": "❌ No audit found (checked DeFiLlama, GitHub, DDG, website)",
        "audit_source": "none",
        "audit_links": [],
    }
