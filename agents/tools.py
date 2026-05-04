"""Agent tools — functions registered with the LLM via Groq function calling.

Three real external APIs the LLM decides when to invoke:
  • fetch_competitor_listing(asin)  → Amazon HTTP fetch + parse
  • get_keyword_trend(keyword)      → Google Trends via pytrends
  • search_reddit_mentions(query)   → Reddit JSON public search API

Each tool exposes:
  - a JSON schema (passed to Groq in `tools=[...]`)
  - a Python handler (executed when the LLM emits a tool_call)
"""
from __future__ import annotations

import json
from pathlib import Path

import requests

from utils.scraper import scrape_product

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_CATALOG_PATH = _DATA_DIR / "pixii_catalog.json"
_SAMPLE_PATH = _DATA_DIR / "sample_data.json"


# =============================================================================
# Tool 1 — fetch_competitor_listing
# =============================================================================
FETCH_COMPETITOR_SCHEMA = {
    "type": "function",
    "function": {
        "name": "fetch_competitor_listing",
        "description": (
            "Fetch a specific competitor's current Amazon listing by ASIN. "
            "Returns title, top bullets, price, and rating. "
            "Use this when you want to drill into one specific competitor — "
            "e.g., the one whose price changed, or the one ranked above the seller. "
            "Costs one HTTP request to Amazon."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "asin": {
                    "type": "string",
                    "description": "The Amazon ASIN of the competitor (e.g., B0IRC0RE99).",
                }
            },
            "required": ["asin"],
        },
    },
}


def _lookup_sample_competitor(asin: str) -> dict | None:
    """Find a competitor in sample_data.json by matching ASIN against pixii_catalog."""
    try:
        catalog = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
        sample = json.loads(_SAMPLE_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None

    for sku in catalog.get("skus", []):
        asins = sku.get("competitive_set_asins") or []
        if asin in asins:
            idx = asins.index(asin)
            scenario = sample.get(sku["scenario_id"], {})
            competitors = scenario.get("competitors", [])
            if idx < len(competitors):
                return competitors[idx]
    return None


def fetch_competitor_listing(asin: str) -> dict:
    """Try a real Amazon fetch; fall back to sample data if blocked."""
    if not asin:
        return {"error": "asin is required"}

    url = f"https://www.amazon.com/dp/{asin}"
    try:
        data = scrape_product(url)
        return {
            "source": "amazon_live",
            "asin": asin,
            "title": data.get("title", ""),
            "bullets": (data.get("bullets") or [])[:3],
            "price": data.get("price", 0),
            "rating": data.get("rating", 0),
        }
    except Exception:
        sample = _lookup_sample_competitor(asin)
        if sample is None:
            return {
                "source": "not_found",
                "asin": asin,
                "error": "ASIN not found in Amazon (blocked) or in catalog.",
            }
        return {
            "source": "sample_fallback",
            "asin": asin,
            "title": sample.get("title", ""),
            "bullets": (sample.get("bullets") or [])[:3],
            "price": sample.get("price", 0),
            "rating": sample.get("rating", 0),
        }


# =============================================================================
# Tool 2 — get_keyword_trend
# =============================================================================
GET_TREND_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_keyword_trend",
        "description": (
            "Return Google Trends interest (0-100) and trend direction for a "
            "keyword over the last 30 days. Use this to validate whether a "
            "'missing keyword' has real search demand before recommending the "
            "seller add it to their listing. Calls Google Trends via HTTP."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": "The keyword or short phrase to look up (e.g., 'non-slip', 'eco-friendly yoga mat').",
                }
            },
            "required": ["keyword"],
        },
    },
}


def _heuristic_interest(keyword: str) -> int:
    """Stable estimate when Google Trends is unavailable."""
    base = max(15, 70 - len(keyword) * 2)
    return min(100, base)


_TREND_CACHE: dict[str, dict] = {}


def get_keyword_trend(keyword: str) -> dict:
    """Real call to Google Trends; deterministic heuristic on failure."""
    if not keyword or not keyword.strip():
        return {"error": "keyword is required"}

    keyword = keyword.strip()

    cache_key = keyword.lower()
    if cache_key in _TREND_CACHE:
        cached = dict(_TREND_CACHE[cache_key])
        cached["source"] = cached.get("source", "google_trends") + "_cached"
        return cached

    try:
        from pytrends.request import TrendReq

        # retries=0 avoids a pytrends/urllib3 v2 incompatibility (Retry.__init__
        # signature changed). With retries=0 pytrends never instantiates Retry.
        pytrends = TrendReq(hl="en-US", tz=360, timeout=(5, 10), retries=0)
        pytrends.build_payload([keyword], timeframe="today 1-m", geo="")
        df = pytrends.interest_over_time()

        if df.empty or keyword not in df.columns:
            return {
                "source": "google_trends",
                "keyword": keyword,
                "interest": 0,
                "trend": "no_data",
            }

        scores = [int(s) for s in df[keyword].tolist() if int(s) >= 0]
        if not scores:
            return {
                "source": "google_trends",
                "keyword": keyword,
                "interest": 0,
                "trend": "no_data",
            }

        avg = int(sum(scores) / len(scores))
        half = max(1, len(scores) // 2)
        first = sum(scores[:half]) / half
        second = sum(scores[half:]) / max(1, len(scores) - half)
        if second > first * 1.15:
            trend = "rising"
        elif second < first * 0.85:
            trend = "falling"
        else:
            trend = "flat"

        result = {
            "source": "google_trends",
            "keyword": keyword,
            "interest": avg,
            "trend": trend,
        }
        _TREND_CACHE[cache_key] = result
        return result

    except Exception as exc:
        return {
            "source": "heuristic_fallback",
            "keyword": keyword,
            "interest": _heuristic_interest(keyword),
            "trend": "unknown",
            "note": f"Google Trends unavailable: {exc}",
        }


# =============================================================================
# Tool 3 — search_reddit_mentions
# =============================================================================
SEARCH_REDDIT_SCHEMA = {
    "type": "function",
    "function": {
        "name": "search_reddit_mentions",
        "description": (
            "Search Reddit for recent public posts mentioning a brand name "
            "or product category. Returns up to 5 recent posts with title, "
            "subreddit, score, and comment count. Use this to gauge how the "
            "seller's brand or category is being talked about outside Amazon — "
            "complaints, recommendations, comparisons. Costs one HTTP request."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Brand name or short product category phrase (e.g., 'ZenFlow yoga mat', 'home gym bands').",
                }
            },
            "required": ["query"],
        },
    },
}

_REDDIT_HEADERS = {
    "User-Agent": "ORACLE/1.0 (Pixii prototype; +https://example.com)",
    "Accept": "application/json",
}


def search_reddit_mentions(query: str) -> dict:
    """Public Reddit search — no auth required for read."""
    if not query or not query.strip():
        return {"error": "query is required"}

    query = query.strip()
    url = "https://www.reddit.com/search.json"
    params = {"q": query, "sort": "new", "limit": 8, "t": "month"}

    try:
        resp = requests.get(url, headers=_REDDIT_HEADERS, params=params, timeout=10)
        if resp.status_code != 200:
            return {
                "source": "reddit",
                "query": query,
                "error": f"HTTP {resp.status_code}",
                "posts": [],
            }
        data = resp.json()
        posts = []
        for child in (data.get("data", {}).get("children") or [])[:5]:
            post = child.get("data") or {}
            posts.append({
                "title": (post.get("title") or "")[:140],
                "subreddit": post.get("subreddit", ""),
                "score": int(post.get("score", 0) or 0),
                "num_comments": int(post.get("num_comments", 0) or 0),
            })
        return {
            "source": "reddit",
            "query": query,
            "posts": posts,
            "count": len(posts),
        }
    except Exception as exc:
        return {"source": "reddit", "query": query, "error": str(exc), "posts": []}


# =============================================================================
# Registry — passed to the Groq function-calling API
# =============================================================================
TOOL_SCHEMAS: list[dict] = [
    FETCH_COMPETITOR_SCHEMA,
    GET_TREND_SCHEMA,
    SEARCH_REDDIT_SCHEMA,
]

TOOL_REGISTRY: dict[str, callable] = {
    "fetch_competitor_listing": fetch_competitor_listing,
    "get_keyword_trend": get_keyword_trend,
    "search_reddit_mentions": search_reddit_mentions,
}
