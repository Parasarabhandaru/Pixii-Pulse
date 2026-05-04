"""ORACLE pipeline orchestrator.

scan -> investigate (agentic, calls 2 tools) -> analyse -> decide -> execute -> 3 cards.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agents import analyst, decider, executor, investigator, scanner

_TOKEN_RATE_USD = 0.000003  # placeholder — Groq free tier is effectively $0


def _sku_context_for(scenario_id: str) -> dict | None:
    """Pull the matching SKU record from Pixii's simulated catalog, if any."""
    if not scenario_id or scenario_id == "live":
        return None
    try:
        from utils.pixii_simulator import get_skus
        for sku in get_skus():
            if sku.get("scenario_id") == scenario_id:
                return sku
    except Exception as exc:
        print(f"[main] pixii catalog lookup failed: {exc}")
    return None


def _run(scan_data: dict, sku_context: dict | None = None) -> dict:
    """Shared post-scan pipeline: investigator → analyst → decider → executor."""
    # Make Pixii's per-SKU metadata visible to the analyst (used for pricing
    # opportunity detection). Stays None for live mode without catalog match.
    scan_data["sku_context"] = sku_context
    investigation = investigator.investigate(scan_data, sku_context)
    findings = analyst.analyse(scan_data)
    priorities = decider.decide(findings)
    cards = executor.execute(priorities, scan_data)
    return {
        "cards": cards,
        "investigation": investigation,
        "scenario_id": scan_data.get("scenario_id", "live"),
    }


def run_pipeline(urls: list[str]) -> dict:
    """Live pipeline. URLs first, falls back to sample data on scrape failure.

    Returns {"cards": [...], "investigation": {...}, "scenario_id": str}.
    """
    scan_data = scanner.scan(urls)
    sku_context = _sku_context_for(scan_data.get("scenario_id", ""))
    return _run(scan_data, sku_context)


def run_pipeline_for_scenario(scenario_id: str) -> dict:
    """Demo pipeline. Skips the scraper, uses sample data + Pixii SKU context."""
    scan_data = scanner.load_scenario(scenario_id)
    sku_context = _sku_context_for(scenario_id)
    return _run(scan_data, sku_context)


def token_cost_summary(payload) -> dict:
    """Sum tokens across the payload, estimate cost, format for display.

    Accepts either the new dict shape ({"cards": [...]}) or a bare list of cards.
    """
    cards = payload["cards"] if isinstance(payload, dict) else (payload or [])
    total_tokens = sum(int(item.get("tokens_used") or 0) for item in cards)
    estimated_cost = total_tokens * _TOKEN_RATE_USD
    cost_display = "Free tier" if estimated_cost <= 0 else f"${estimated_cost:.4f}"
    return {
        "total_tokens": total_tokens,
        "estimated_cost_usd": estimated_cost,
        "cost_display": cost_display,
    }


if __name__ == "__main__":
    import json

    result = run_pipeline_for_scenario("yoga_mat")
    print("=== INVESTIGATION TRACE ===")
    inv = result["investigation"]
    for call in inv["tool_calls"]:
        print(
            f"[iter {call['iteration']}] "
            f"{call['tool']}({json.dumps(call['args'])}) -> {call['result_preview']}"
        )
    print()
    print("=== RESEARCH NOTES ===")
    print(inv["research_notes"])
    print()
    print("=== CARDS ===")
    print(json.dumps(result["cards"], indent=2))
    print()
    print(json.dumps(token_cost_summary(result), indent=2))
