"""Simulates the Pixii data layer.

In production, ORACLE would read directly from Pixii's database — the
seller's catalog, conversion trends, ad spend, and competitive set are
all already there. This module fakes that integration using a static
JSON file (data/pixii_catalog.json) so the prototype can demonstrate
what the URL-input form would look like AFTER Pixii integration: gone.
"""
from __future__ import annotations

import json
from pathlib import Path

_CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "pixii_catalog.json"


def get_catalog() -> dict:
    """Load PrimeBrands Co.'s catalog as Pixii would expose it."""
    with _CATALOG_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def get_skus() -> list[dict]:
    return get_catalog().get("skus", [])


def pick_priority_sku() -> dict:
    """Return the SKU with the highest priority_score.

    In production this is what Pixii's recommendation engine surfaces:
    the listing whose conversion rate, ad efficiency, or rank is most
    deteriorating. Today's briefing should focus here.
    """
    skus = get_skus()
    if not skus:
        raise RuntimeError("Pixii catalog is empty.")
    return max(skus, key=lambda s: int(s.get("priority_score", 0)))


def get_sku(sku_id: str) -> dict:
    for sku in get_skus():
        if sku.get("sku_id") == sku_id:
            return sku
    raise KeyError(f"sku_id '{sku_id}' not found in Pixii catalog")


def fmt_seller_header() -> str:
    cat = get_catalog()
    return f"{cat['seller_name']} (Pixii ID: {cat['seller_id']})"
