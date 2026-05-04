"""SCAN agent — Step 2 in the ORACLE pipeline.

Tries live scrape for the URL list. On any failure, silently falls back to
a matching scenario from data/sample_data.json. The result always has the
same shape: {seller, competitors, scenario_id}.
"""
from __future__ import annotations

import json
from pathlib import Path

from utils.scraper import scrape_product

_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "sample_data.json"


def _load_sample() -> dict:
    with _DATA_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def _pick_scenario(seller_url: str, sample: dict) -> dict:
    """Match URL keywords to a scenario. Default: yoga_mat."""
    url = (seller_url or "").lower()
    routes = [
        (("protein", "whey", "powder"), "protein_powder"),
        (("laptop", "stand", "riser"), "laptop_stand"),
        (("coffee", "grinder", "espresso"), "coffee_grinder"),
        (("resistance", "bands", "band"), "resistance_bands"),
        (("water", "bottle", "flask", "tumbler"), "water_bottle"),
    ]
    for keywords, scenario_id in routes:
        if any(k in url for k in keywords):
            return sample[scenario_id]
    return sample["yoga_mat"]


def scan(urls: list[str]) -> dict:
    """Return {"seller", "competitors", "scenario_id"}.

    On any scrape failure, fall back to a matching sample scenario without
    surfacing the error to callers.
    """
    if not urls:
        raise ValueError("scan() requires at least one URL")

    seller_url = urls[0]
    competitor_urls = [u for u in urls[1:] if u]

    try:
        seller = scrape_product(seller_url)
        competitors = [scrape_product(u) for u in competitor_urls]
        if not competitors:
            raise RuntimeError("no competitor URLs provided — using sample data")
        return {
            "seller": seller,
            "competitors": competitors,
            "scenario_id": "live",
        }
    except Exception as exc:
        print(f"[scanner] live scrape failed ({exc}); using sample fallback")
        scenario = _pick_scenario(seller_url, _load_sample())
        return {
            "seller": scenario["seller"],
            "competitors": scenario["competitors"],
            "scenario_id": scenario["scenario_id"],
        }


def load_scenario(scenario_id: str) -> dict:
    """Load a specific scenario by id. Used by the UI demo mode and scheduler."""
    sample = _load_sample()
    if scenario_id not in sample:
        raise ValueError(
            f"Unknown scenario_id '{scenario_id}'. "
            f"Available: {sorted(sample.keys())}"
        )
    scenario = sample[scenario_id]
    return {
        "seller": scenario["seller"],
        "competitors": scenario["competitors"],
        "scenario_id": scenario["scenario_id"],
    }
