"""ANALYZE agent — Step 3 in the ORACLE pipeline.

Takes the product dict from scanner.scan() and returns a list of finding
objects, each with severity / frequency / revenue_impact (1-10) so the
DECIDE agent can rank them by Oracle Impact Index (OII).

Detail fields needed by the executor (keywords, complaint, gap_reason, etc.)
live under finding["data"] so the executor has a single, predictable place
to look.
"""
from __future__ import annotations

import re
from collections import Counter

from utils.claude_client import call_claude_json
from utils.fx import to_usd, rate_source
from utils.prompts import HOOK_PROMPT, SENTIMENT_PROMPT

_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "it", "its", "this", "that", "are",
    "was", "be", "as", "i", "we", "our", "your", "you", "my", "their",
    "they", "into", "without", "been", "being", "these", "those", "if",
    "than", "then", "so", "yours", "ours", "me", "them", "no", "not",
    "all", "any", "each", "every", "more", "most", "other", "some", "such",
    "only", "own", "same", "very", "can", "will", "just", "now", "up",
    "down", "out", "over", "under", "again", "once", "here", "there",
    "when", "where", "why", "how", "what", "which", "who", "whom", "do",
    "does", "did", "have", "has", "had", "having", "use", "uses", "used",
    "using", "made", "make", "makes", "get", "gets", "great", "good",
    "best", "amazing", "perfect", "love", "really", "also", "one", "two",
    "three", "four", "five",
}

_TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z\-]+")


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or "") if len(t) > 2]


def _tokens_for(product: dict) -> set[str]:
    blob = (product.get("title", "") or "") + " " + " ".join(product.get("bullets", []) or [])
    return {t for t in _tokenize(blob) if t not in _STOPWORDS}


def _keyword_gap(product_dict: dict) -> dict | None:
    """Pure-Python: words in 2+ competitors but absent from seller."""
    seller_tokens = _tokens_for(product_dict["seller"])
    competitors = product_dict.get("competitors", [])
    if not competitors:
        return None

    counter: Counter[str] = Counter()
    for comp in competitors:
        for token in _tokens_for(comp):
            counter[token] += 1

    gaps = [
        (tok, count)
        for tok, count in counter.most_common()
        if count >= 2 and tok not in seller_tokens
    ]
    if not gaps:
        return None

    top = gaps[:10]
    keywords = [tok for tok, _ in top]
    max_count = max(c for _, c in top)

    description = f"Missing keywords found in competitors: {', '.join(keywords[:5])}"
    severity = min(10, len(top))
    frequency = min(10, max_count * 3)
    revenue_impact = 8

    seller_bullets = product_dict["seller"].get("bullets") or [""]
    current_bullet = seller_bullets[0] if seller_bullets else ""

    return {
        "type": "keyword_gap",
        "description": description,
        "severity": severity,
        "frequency": frequency,
        "revenue_impact": revenue_impact,
        "data": {
            "missing_keywords": keywords,
            "current_bullet": current_bullet,
        },
    }


def _sentiment(product_dict: dict) -> dict | None:
    reviews = product_dict["seller"].get("reviews", [])[:20]
    if not reviews:
        return None

    review_blob = "\n".join(f"- {r}" for r in reviews if r)
    try:
        result = call_claude_json(
            SENTIMENT_PROMPT.format(reviews=review_blob), max_tokens=500
        )
    except Exception as exc:
        print(f"[analyst] sentiment call failed: {exc}")
        return None

    complaint = (result.get("top_complaint") or "").strip()
    freq = int(result.get("complaint_frequency") or 0)
    if not complaint or freq <= 0:
        return None

    severity = min(10, freq)
    frequency = min(10, freq)
    revenue_impact = 7

    description = f"Top complaint: {complaint}"
    return {
        "type": "review_complaint",
        "description": description,
        "severity": severity,
        "frequency": frequency,
        "revenue_impact": revenue_impact,
        "data": {
            "complaint": complaint,
            "frequency": freq,
        },
    }


def _hook(product_dict: dict) -> dict | None:
    seller = product_dict["seller"]
    competitors = product_dict.get("competitors", [])
    if not competitors:
        return None

    seller_bullet = (seller.get("bullets") or [""])[0]
    competitor_hooks = "\n".join(
        f"- {c.get('title', '')} | {(c.get('bullets') or [''])[0]}"
        for c in competitors
    )

    try:
        result = call_claude_json(
            HOOK_PROMPT.format(
                seller_title=seller.get("title", ""),
                seller_bullet=seller_bullet,
                competitor_hooks=competitor_hooks,
            ),
            max_tokens=500,
        )
    except Exception as exc:
        print(f"[analyst] hook call failed: {exc}")
        return None

    seller_score = int(result.get("seller_score") or 5)
    competitor_score = int(result.get("best_competitor_score") or 5)
    gap_reason = (result.get("gap_reason") or "").strip()
    gap = max(0, competitor_score - seller_score)

    if gap < 2:
        return None

    severity = min(10, gap * 2)
    frequency = 5
    revenue_impact = 9

    description = f"Hook gap: {gap_reason}"
    return {
        "type": "weak_hook",
        "description": description,
        "severity": severity,
        "frequency": frequency,
        "revenue_impact": revenue_impact,
        "data": {
            "seller_score": seller_score,
            "competitor_score": competitor_score,
            "gap_reason": gap_reason,
            "current_title": seller.get("title", ""),
        },
    }


def _pricing_opportunity(product_dict: dict) -> dict | None:
    """Detect cross-marketplace pricing gap using live FX rates.

    Reads Pixii's per-SKU marketplaces from product_dict["sku_context"], converts
    every local price to USD via the open.er-api.com FX API, and surfaces the
    biggest deviation if it exceeds 10% relative to the median.
    """
    sku_context = product_dict.get("sku_context") or {}
    marketplaces = sku_context.get("marketplaces") or {}
    if len(marketplaces) < 2:
        return None

    usd_by_region: dict[str, float] = {}
    local_by_region: dict[str, dict] = {}
    for region, info in marketplaces.items():
        currency = info.get("currency") or "USD"
        amount = info.get("price_local") or info.get("price_usd") or 0
        if amount > 0:
            usd_value = round(to_usd(amount, currency), 2)
            usd_by_region[region] = usd_value
            local_by_region[region] = {
                "local": amount,
                "currency": currency,
                "usd": usd_value,
            }

    if len(usd_by_region) < 2:
        return None

    sorted_usd = sorted(usd_by_region.values())
    median_usd = sorted_usd[len(sorted_usd) // 2]
    if median_usd <= 0:
        return None

    deviations = [
        (region, price, (price - median_usd) / median_usd)
        for region, price in usd_by_region.items()
    ]
    deviations.sort(key=lambda x: abs(x[2]), reverse=True)
    biggest_region, biggest_price, biggest_pct = deviations[0]

    if abs(biggest_pct) < 0.10:  # below 10% — not material
        return None

    direction = "above" if biggest_pct > 0 else "below"
    description = (
        f"Pricing gap on {biggest_region}: marketplace is "
        f"{abs(biggest_pct) * 100:.1f}% {direction} the rest of your portfolio "
        f"(${biggest_price:.2f} vs median ${median_usd:.2f} after live FX conversion)."
    )

    severity = min(10, int(abs(biggest_pct) * 50))
    frequency = 6
    revenue_impact = 9

    return {
        "type": "pricing_opportunity",
        "description": description,
        "severity": severity,
        "frequency": frequency,
        "revenue_impact": revenue_impact,
        "data": {
            "region": biggest_region,
            "current_usd_price": biggest_price,
            "median_usd_price": median_usd,
            "deviation_pct": round(biggest_pct * 100, 1),
            "direction": direction,
            "all_marketplaces": local_by_region,
            "fx_source": rate_source(),
        },
    }


def _fallback_finding(reason: str) -> dict:
    return {
        "type": "keyword_gap",
        "description": f"Analysis unavailable — {reason}",
        "severity": 1,
        "frequency": 1,
        "revenue_impact": 1,
        "data": {"missing_keywords": [], "current_bullet": ""},
    }


def analyse(product_dict: dict) -> list[dict]:
    """Run all 3 analyses and return a flat findings list."""
    findings: list[dict] = []
    for fn in (_keyword_gap, _sentiment, _hook, _pricing_opportunity):
        try:
            finding = fn(product_dict)
        except Exception as exc:
            print(f"[analyst] {fn.__name__} crashed: {exc}")
            finding = _fallback_finding("please retry.")
        if finding is not None:
            findings.append(finding)

    if not findings:
        findings = [_fallback_finding("please retry.")]
    return findings
