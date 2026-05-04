"""EXECUTE agent — Step 5 in the ORACLE pipeline.

Takes the 3 ranked priorities from decider.decide() and produces the final
copy-paste-ready text for each. One LLM call per priority. Token usage is
tracked and returned alongside each output for cost visibility.
"""
from __future__ import annotations

import json

from utils.claude_client import call_with_tokens
from utils.prompts import (
    LISTING_REWRITE_PROMPT,
    PRICING_REWRITE_PROMPT,
    REVIEW_REPLY_PROMPT,
    SOCIAL_PROMPT,
)

_FALLBACK = "Output unavailable — please retry."


def _execute_listing(priority: dict, product_dict: dict) -> tuple[str, int]:
    data = priority.get("data", {})
    keywords = data.get("missing_keywords") or []
    current_bullet = data.get("current_bullet") or (
        (product_dict["seller"].get("bullets") or [""])[0]
    )
    prompt = LISTING_REWRITE_PROMPT.format(
        current_bullet=current_bullet,
        keywords=", ".join(keywords),
        issue=priority.get("description", ""),
    )
    text, tokens = call_with_tokens(prompt, max_tokens=1000)
    return text.strip(), tokens


def _execute_review(priority: dict, product_dict: dict) -> tuple[str, int]:
    data = priority.get("data", {})
    prompt = REVIEW_REPLY_PROMPT.format(
        complaint=data.get("complaint", priority.get("description", "")),
        frequency=data.get("frequency", 0),
    )
    text, tokens = call_with_tokens(prompt, max_tokens=1000)
    return text.strip(), tokens


def _execute_social(priority: dict, product_dict: dict) -> tuple[str, int]:
    data = priority.get("data", {})
    prompt = SOCIAL_PROMPT.format(
        product_title=product_dict["seller"].get("title", ""),
        gap=data.get("gap_reason", priority.get("description", "")),
    )
    text, tokens = call_with_tokens(prompt, max_tokens=1000)
    return text.strip(), tokens


def _execute_pricing(priority: dict, product_dict: dict) -> tuple[str, int]:
    data = priority.get("data", {})
    pricing_data = json.dumps({
        "marketplace_with_gap": data.get("region"),
        "current_usd_price": data.get("current_usd_price"),
        "median_usd_price": data.get("median_usd_price"),
        "deviation_pct": data.get("deviation_pct"),
        "direction": data.get("direction"),
        "all_marketplaces": data.get("all_marketplaces"),
        "fx_rates_source": data.get("fx_source", "live_api"),
    }, indent=2)
    prompt = PRICING_REWRITE_PROMPT.format(
        pricing_data=pricing_data,
        issue=priority.get("description", ""),
    )
    text, tokens = call_with_tokens(prompt, max_tokens=600)
    return text.strip(), tokens


_DISPATCH = {
    "listing": _execute_listing,
    "review": _execute_review,
    "social": _execute_social,
    "pricing": _execute_pricing,
}


def execute(priorities: list[dict], product_dict: dict) -> list[dict]:
    """Return the final 3-card payload with ready-to-use output text."""
    payload: list[dict] = []
    scenario_id = product_dict.get("scenario_id", "live")

    for priority in priorities:
        category = priority.get("category", "listing")
        try:
            output, tokens = _DISPATCH[category](priority, product_dict)
            if not output:
                output = _FALLBACK
        except Exception as exc:
            print(f"[executor] {category} call failed: {exc}")
            output = _FALLBACK
            tokens = 0

        payload.append({
            "rank": priority["rank"],
            "category": category,
            "issue": priority["description"],
            "oii": priority["oii"],
            "severity": priority.get("severity", 0),
            "frequency": priority.get("frequency", 0),
            "revenue_impact": priority.get("revenue_impact", 0),
            "output": output,
            "tokens_used": tokens,
            "scenario_id": scenario_id,
        })
    return payload
