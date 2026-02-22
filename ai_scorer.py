from __future__ import annotations

"""
Verichains LeadHunter — AI Scorer (Google Gemini / Anthropic Claude / OpenAI)
Handles: Lead scoring, noise filtering, project enrichment.
Auto-detects which API key is available. Gemini > Anthropic > OpenAI.
"""

import json
import config

# ================================================================
#  Setup AI Client — auto-detect provider
# ================================================================

client = None
provider = config.AI_PROVIDER  # "gemini", "anthropic", "openai", or "none"

if provider == "gemini":
    try:
        from google import genai
        client = genai.Client(api_key=config.GEMINI_API_KEY)
        print(f"[AI Scorer] ✅ Using Google Gemini ({config.GEMINI_MODEL})")
    except Exception as e:
        print(f"[AI Scorer] ❌ Gemini init failed: {e}")
        client = None
elif provider == "anthropic":
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
        print(f"[AI Scorer] ✅ Using Anthropic Claude ({config.ANTHROPIC_MODEL})")
    except Exception as e:
        print(f"[AI Scorer] ❌ Anthropic init failed: {e}")
        client = None
elif provider == "openai":
    try:
        from openai import OpenAI
        client = OpenAI(api_key=config.OPENAI_API_KEY)
        print(f"[AI Scorer] ✅ Using OpenAI ({config.OPENAI_MODEL})")
    except Exception as e:
        print(f"[AI Scorer] ❌ OpenAI init failed: {e}")
        client = None
else:
    print("[AI Scorer] ⚠️  No AI key configured. Set GEMINI_API_KEY, ANTHROPIC_API_KEY, or OPENAI_API_KEY in .env")


# ================================================================
#  SCORING SYSTEM PROMPT — The brain of LeadHunter
# ================================================================

SCORING_SYSTEM_PROMPT = """You are a Lead Scoring AI for Verichains, a blockchain security firm specializing in:
- Smart Contract Audit (DeFi, GameFi, RWA, Oracle, Prediction Market)
- Cryptography Audit (ZK, MPC, TSS) — our STRONGEST competitive advantage
- Blockchain L1/L2 Audit — our STRONGEST competitive advantage
- Penetration Testing

Your job: Score each project lead from 0-100 and provide a brief summary.

## SCORING RUBRIC (Total: 100 points)

### General Criteria (60 points max):
- Funding & Budget (15pts): $1.5M-$5M = 15 (sweet spot). >$10M = 10 (high competition). <$1M = 5. None = 2.
- Backer Quality (10pts): Tier 1 VC (a16z, Paradigm, Binance Labs, Polychain, Sequoia, Andreessen) = 10. Tier 2 = 6. Unknown = 2.
- Timeline Urgency (10pts): Mainnet <1 month = 10. 1-3 months = 7. >6 months = 3. Unknown = 5.
- Audit Status (10pts): No audit ever = 10. Last audit >6 months ago = 7. Recently audited by competitor = 2.
- Team Profile (5pts): Doxxed with track record = 5. Doxxed = 3. Anonymous = 1.
- Social Engagement (5pts): Organic community >10K = 5. 1-10K = 3. <1K or bot-heavy = 1.
- Verichains Moat Fit (5pts): ZK/Crypto/L1/L2 = 5. Complex DeFi = 3. Simple fork = 1.

### Category-Specific Criteria (40 points max):

For DeFi:
- Novelty of Logic (15): Novel AMM/Yield/Oracle = 15. Modified fork = 8. Pure fork = 3.
- Protocol Complexity (10): Cross-chain multi-contract = 10. Simple swap = 2.
- TVL (10): >$10M = 10. $1-10M = 7. <$1M = 3.
- Token Launch (5): IDO planned = 5. No token = 1.

For GameFi:
- On-chain vs Off-chain (15): Fully on-chain = 15. Off-chain heavy = 10 (pitch PenTest). Hybrid = 12.
- Token Economy (10): Complex = 10. Simple = 3.
- Studio Reputation (10): Established = 10. Unknown = 2.
- Platform (5): Multi-platform = 5. Single = 3.

For RWA:
- Compliance Need (15): Regulated jurisdiction = 15. Unregulated = 3.
- TradFi Partners (10): Banks = 10. None = 2.
- Asset Complexity (10): Securities = 10. Simple tokens = 3.
- Legal Entity (5): Licensed = 5. No entity = 1.

For ZK/MPC/TSS (Verichains specialty):
- Crypto Novelty (15): Custom constructions = 15. Library usage = 3.
- Code Language (10): Rust/Go/C++ = 10. Solidity = 5.
- Academic Backing (10): PhD + papers = 10. No formal = 2.
- Value Protected (5): >$50M = 5. <$5M = 1.

For L1/L2:
- Consensus Novelty (15): Custom = 15. Fork = 3.
- Bridge Component (10): Has bridge = 10. No bridge = 3.
- Ecosystem Size (10): Active dApps = 10. Empty = 2.
- Code Language (5): Rust/Go/C++ = 5. EVM-only = 2.

## OUTPUT FORMAT (strict JSON):
{
    "name": "Project Name",
    "category": "DeFi|GameFi|RWA|ZK|L1-L2|Other",
    "score": 75,
    "priority": "HOT|WARM|MONITOR|LOW",
    "funding": "$3M Seed from Paradigm",
    "tech": "Solidity, EVM",
    "audit_status": "No audit found",
    "summary": "2-3 sentence brief on why this is a good lead and what service to pitch",
    "pitch_services": ["Smart Contract Audit", "Penetration Testing"],
    "signals": ["Just raised funding", "Novel AMM design"]
}

Priority rules: score >= 80 = HOT, 60-79 = WARM, 40-59 = MONITOR, <40 = LOW.
If information is missing, make reasonable estimates and note uncertainty.
Always respond with valid JSON only, no markdown formatting."""


# ================================================================
#  NOISE FILTER SYSTEM PROMPT
# ================================================================

NOISE_FILTER_PROMPT = """You are a noise filter for a blockchain security firm's lead generation system.
Your job: Determine if a GitHub change or social media post represents a MEANINGFUL smart contract or protocol update that might need a security audit.

MEANINGFUL changes (return true):
- New or modified smart contract logic (.sol, .rs, .move files in /contracts, /src, /circuits)
- Protocol upgrade (new version, migration, consensus changes)
- New features affecting security (new pools, new token standards, bridge changes)
- Dependency updates to security-critical libraries (OpenZeppelin, etc.)

NOT meaningful (return false):
- Documentation updates (README, docs/, comments)
- UI/frontend changes
- Test file changes only
- CI/CD pipeline changes
- Refactoring without logic changes
- Marketing/social media fluff
- Typo fixes

OUTPUT FORMAT (strict JSON):
{
    "is_meaningful": true,
    "confidence": 0.85,
    "reason": "PR introduces new staking contract with novel reward distribution logic"
}

Always respond with valid JSON only."""


# ================================================================
#  Unified Chat Function (supports all providers)
# ================================================================

import time as _time

_last_call_time = 0.0
_GEMINI_MIN_INTERVAL = 5.0  # 15 RPM → 1 call per 5 seconds (safe margin)
_consecutive_rate_limits = 0
_circuit_broken = False  # When True, skip retries entirely


def reset_circuit_breaker():
    """Reset circuit breaker between scan runs."""
    global _consecutive_rate_limits, _circuit_broken
    _consecutive_rate_limits = 0
    _circuit_broken = False


def _chat(system_prompt: str, user_prompt: str, max_tokens: int = None) -> str | None:
    """Send a chat request to the configured AI provider. Returns raw text.
    Includes rate limiting for Gemini and retry with exponential backoff.
    Circuit breaker: after 2 consecutive 429s, skips retries for remaining calls."""
    global _last_call_time, _consecutive_rate_limits, _circuit_broken
    if not client:
        return None

    max_tokens = max_tokens or config.AI_MAX_TOKENS

    # Circuit breaker — quota exhausted, skip retries
    if _circuit_broken:
        return None

    # Rate limiting for Gemini free tier (15 RPM)
    if provider == "gemini":
        elapsed = _time.time() - _last_call_time
        if elapsed < _GEMINI_MIN_INTERVAL:
            wait = _GEMINI_MIN_INTERVAL - elapsed
            _time.sleep(wait)

    max_retries = 3
    for attempt in range(max_retries + 1):
        try:
            _last_call_time = _time.time()

            if provider == "gemini":
                from google.genai import types
                response = client.models.generate_content(
                    model=config.GEMINI_MODEL,
                    contents=user_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        max_output_tokens=max_tokens,
                        temperature=0.3,
                        response_mime_type="application/json",
                    ),
                )
                _consecutive_rate_limits = 0  # Success resets counter
                return response.text

            elif provider == "anthropic":
                response = client.messages.create(
                    model=config.ANTHROPIC_MODEL,
                    max_tokens=max_tokens,
                    temperature=0.3,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                )
                _consecutive_rate_limits = 0
                return response.content[0].text

            elif provider == "openai":
                response = client.chat.completions.create(
                    model=config.OPENAI_MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    max_tokens=max_tokens,
                    temperature=0.3,
                    response_format={"type": "json_object"},
                )
                _consecutive_rate_limits = 0
                return response.choices[0].message.content

        except Exception as e:
            error_str = str(e)
            is_rate_limit = "429" in error_str or "RESOURCE_EXHAUSTED" in error_str or "rate" in error_str.lower()

            if is_rate_limit:
                _consecutive_rate_limits += 1
                # Circuit breaker: after 2 consecutive rate limits, give up for this scan
                if _consecutive_rate_limits >= 2:
                    _circuit_broken = True
                    print(f"[AI Scorer] 🔴 Quota exhausted — switching to heuristic for remaining leads")
                    return None
                if attempt < max_retries:
                    wait = 10 * (2 ** attempt)  # 10s, 20s, 40s
                    print(f"[AI Scorer] ⏳ Rate limited. Retry {attempt + 1}/{max_retries} in {wait}s...")
                    _time.sleep(wait)
                    continue
            print(f"[AI Scorer] ❌ Chat failed ({provider}): {e}")
            return None


def _parse_json(text: str) -> dict | None:
    """Extract JSON from AI response, handling markdown code blocks."""
    if not text:
        return None
    # Strip markdown code block if present
    cleaned = text.strip()
    if cleaned.startswith("```"):
        # Remove opening ```json or ```
        first_newline = cleaned.index("\n")
        last_fence = cleaned.rfind("```")
        cleaned = cleaned[first_newline + 1:last_fence].strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        print(f"[AI Scorer] ❌ JSON parse failed: {e}")
        print(f"  Raw text: {text[:200]}...")
        return None


# ================================================================
#  Public API
# ================================================================

def score_lead(raw_data: str, source: str = "unknown") -> dict | None:
    """
    Score a project lead using AI.

    Args:
        raw_data: String with all known info about the project
        source: Where we found this lead (DeFiLlama, RootData, etc.)

    Returns:
        Dict with scoring results, or None on failure
    """
    if not client:
        print(f"[AI Scorer] ⚠️  No AI configured. Set GEMINI_API_KEY, ANTHROPIC_API_KEY, or OPENAI_API_KEY.")
        return None

    user_prompt = f"""Score this blockchain project lead.
Source: {source}

Project Data:
{raw_data}

Return JSON score following the rubric."""

    text = _chat(SCORING_SYSTEM_PROMPT, user_prompt)
    result = _parse_json(text)
    if result:
        result["source"] = source
    return result


def filter_noise(change_description: str) -> dict | None:
    """
    Determine if a GitHub/social change is meaningful for security auditing.

    Args:
        change_description: Description of the change (PR title, diff summary, tweet text)

    Returns:
        Dict with {is_meaningful, confidence, reason}, or None on failure
    """
    if not client:
        return None

    text = _chat(NOISE_FILTER_PROMPT, change_description, max_tokens=300)
    return _parse_json(text)


def score_leads_batch(leads_raw: list[dict], source: str = "unknown") -> list[dict]:
    """
    Score multiple leads efficiently.
    Groups them into a single prompt to minimize API calls.
    """
    if not client or not leads_raw:
        return []

    # Process in chunks of 5 to avoid token limits
    results = []
    for i in range(0, len(leads_raw), 5):
        chunk = leads_raw[i:i + 5]
        combined = "\n\n---\n\n".join(
            [f"PROJECT {j+1}:\n{json.dumps(lead, indent=2, ensure_ascii=False)}"
             for j, lead in enumerate(chunk)]
        )

        user_prompt = f"""Score these {len(chunk)} blockchain project leads.
Source: {source}

{combined}

Return a JSON object with key "leads" containing an array of scored results, one per project.
Each result should follow the scoring rubric."""

        text = _chat(SCORING_SYSTEM_PROMPT, user_prompt, max_tokens=config.AI_MAX_TOKENS * 2)
        parsed = _parse_json(text)
        if parsed:
            batch_results = parsed.get("leads", [parsed] if "name" in parsed else [])
            for r in batch_results:
                r["source"] = source
            results.extend(batch_results)
        else:
            # Fallback: score individually
            for lead in chunk:
                result = score_lead(json.dumps(lead, ensure_ascii=False), source)
                if result:
                    results.append(result)

    return results


# ---- Quick test ----
if __name__ == "__main__":
    test_data = """
    Project: NovaSwap
    Category: DeFi (DEX)
    Description: Novel AMM with concentrated liquidity and cross-chain swaps
    Funding: $2.5M Seed from Polychain Capital
    Chain: Ethereum + Arbitrum
    Team: CTO ex-Uniswap, Lead Dev ex-Aave
    GitHub: Active, 45 contributors
    TVL: $0 (pre-launch)
    Token: TGE planned Q2 2026
    Audit: None
    """
    result = score_lead(test_data, "RootData")
    if result:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("Configure ANTHROPIC_API_KEY or OPENAI_API_KEY in .env to test scoring.")
