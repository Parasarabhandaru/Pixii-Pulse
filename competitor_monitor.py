"""Competitor change detector — price drops, new keywords, rating drops.

Compares each competitor against the previous snapshot stored in
data/competitor_snapshots.json. On any of the three change types, sends
an alert and prints to console.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from agents.scanner import load_scenario
from utils.notifier import send_alert

_SNAPSHOT_PATH = Path(__file__).resolve().parent / "data" / "competitor_snapshots.json"

_PRICE_DROP_THRESHOLD = 0.05
_RATING_FLOOR = 4.0
_NEW_KEYWORD_THRESHOLD = 3
_TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z\-]+")

_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "for", "with", "of", "to",
    "in", "on", "at", "by", "from", "is", "it", "its", "this", "that",
}


def _load_snapshots() -> dict:
    if not _SNAPSHOT_PATH.exists():
        _SNAPSHOT_PATH.write_text("{}", encoding="utf-8")
        return {}
    try:
        return json.loads(_SNAPSHOT_PATH.read_text(encoding="utf-8") or "{}")
    except json.JSONDecodeError:
        return {}


def _save_snapshots(snapshots: dict) -> None:
    _SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _SNAPSHOT_PATH.write_text(
        json.dumps(snapshots, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _competitor_key(competitor: dict, idx: int) -> str:
    return competitor.get("title") or f"competitor_{idx}"


def _tokenize(text: str) -> set[str]:
    return {
        t.lower()
        for t in _TOKEN_RE.findall(text or "")
        if len(t) > 2 and t.lower() not in _STOPWORDS
    }


def _competitor_tokens(competitor: dict) -> set[str]:
    blob = (competitor.get("title", "") or "") + " " + " ".join(
        competitor.get("bullets", []) or []
    )
    return _tokenize(blob)


def _detect_changes(scenario_id: str, key: str, current: dict, previous: dict) -> list[dict]:
    alerts: list[dict] = []

    # Price drop
    old_price = float(previous.get("price") or 0)
    new_price = float(current.get("price") or 0)
    if old_price > 0 and new_price > 0 and new_price < old_price:
        drop_pct = (old_price - new_price) / old_price
        if drop_pct >= _PRICE_DROP_THRESHOLD:
            alerts.append({
                "type": "price_drop",
                "subject": f"Pixii Pulse — Competitor price drop on {scenario_id}",
                "body": (
                    f"Scenario: {scenario_id}\n"
                    f"Competitor: {key}\n"
                    f"Old price: ${old_price:.2f} -> New price: ${new_price:.2f} "
                    f"(-{drop_pct * 100:.1f}%)\n"
                    f"Suggested: highlight your premium value."
                ),
            })

    # New keywords
    old_tokens = set(previous.get("tokens") or [])
    new_tokens = _competitor_tokens(current)
    added = sorted(new_tokens - old_tokens)
    if old_tokens and len(added) >= _NEW_KEYWORD_THRESHOLD:
        alerts.append({
            "type": "new_keywords",
            "subject": f"Pixii Pulse — Competitor added keywords on {scenario_id}",
            "body": (
                f"Scenario: {scenario_id}\n"
                f"Competitor: {key}\n"
                f"Competitor added keywords: {', '.join(added[:10])}\n"
                f"Consider adding to your listing."
            ),
        })

    # Rating drop
    old_rating = float(previous.get("rating") or 0)
    new_rating = float(current.get("rating") or 0)
    if old_rating >= _RATING_FLOOR and new_rating < _RATING_FLOOR:
        alerts.append({
            "type": "rating_drop",
            "subject": f"Pixii Pulse — Competitor rating drop on {scenario_id}",
            "body": (
                f"Scenario: {scenario_id}\n"
                f"Competitor: {key}\n"
                f"Rating dropped to {new_rating:.1f} (was {old_rating:.1f}).\n"
                f"Opportunity to capture dissatisfied customers."
            ),
        })

    return alerts


def _print_alert(alert: dict) -> None:
    print("=" * 60)
    print("Pixii Pulse Competitor Monitor Alert")
    print("-" * 60)
    print(f"Type: {alert['type']}")
    print(alert["body"])
    print("=" * 60)


def monitor_competitors(product_dict: dict, scenario_id: str) -> dict:
    snapshots = _load_snapshots()
    previous_by_key = snapshots.get(scenario_id, {})

    triggered: list[dict] = []
    new_snapshot: dict = {}

    for idx, competitor in enumerate(product_dict.get("competitors", [])):
        key = _competitor_key(competitor, idx)
        previous = previous_by_key.get(key, {})

        alerts = _detect_changes(scenario_id, key, competitor, previous)
        for alert in alerts:
            _print_alert(alert)
            send_alert(
                alert["subject"],
                alert["body"],
                kind="competitor",
                scenario_id=scenario_id,
                keyword=alert.get("type"),
                severity=7 if alert["type"] == "price_drop" else 5,
            )
            triggered.append({"competitor": key, **alert})

        new_snapshot[key] = {
            "price": float(competitor.get("price") or 0),
            "rating": float(competitor.get("rating") or 0),
            "tokens": sorted(_competitor_tokens(competitor)),
        }

    snapshots[scenario_id] = new_snapshot
    _save_snapshots(snapshots)

    return {"scenario_id": scenario_id, "triggered": triggered}


def demo_trigger() -> dict:
    """Simulate a 15% price drop on a resistance_bands competitor and run monitor."""
    scenario = load_scenario("resistance_bands")
    if not scenario["competitors"]:
        return {"scenario_id": "resistance_bands", "triggered": []}

    competitor = scenario["competitors"][0]
    key = _competitor_key(competitor, 0)
    old_price = 24.99
    new_price = round(old_price * 0.85, 2)

    # Seed the snapshot with the higher "previous" price so the current price
    # registers as a 15% drop.
    snapshots = _load_snapshots()
    snapshots["resistance_bands"] = {
        key: {
            "price": old_price,
            "rating": float(competitor.get("rating") or 0),
            "tokens": sorted(_competitor_tokens(competitor)),
        }
    }
    _save_snapshots(snapshots)

    competitor["price"] = new_price
    return monitor_competitors(scenario, "resistance_bands")


if __name__ == "__main__":
    print(demo_trigger())
