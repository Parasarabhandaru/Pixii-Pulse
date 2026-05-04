"""Review monitor — detects new complaint patterns and alerts.

Compares the current review set for a scenario against the previous
snapshot stored in data/review_snapshots.json. If any complaint keyword
appears 3+ times in *new* reviews, fires send_alert().
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from agents.scanner import load_scenario
from utils.notifier import send_alert

_SNAPSHOT_PATH = Path(__file__).resolve().parent / "data" / "review_snapshots.json"

_COMPLAINT_KEYWORDS = [
    "clump", "snap", "loud", "smell", "break", "broke", "crack", "leak",
    "cheap", "return", "refund", "disappoint", "poor", "bad", "worst",
]

_THRESHOLD = 3
_TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z\-]+")


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


def _tokens_in(reviews: list[str]) -> Counter:
    counter: Counter = Counter()
    for review in reviews:
        for tok in _TOKEN_RE.findall((review or "").lower()):
            counter[tok] += 1
    return counter


def _count_complaint(token_counts: Counter, stem: str) -> int:
    """Match `snap` against tokens like `snap`, `snaps`, `snapped`, `snapping`."""
    return sum(count for tok, count in token_counts.items() if tok.startswith(stem))


def _new_reviews(current: list[str], previous: list[str]) -> list[str]:
    seen = set(previous)
    return [r for r in current if r not in seen]


def watch_reviews(product_dict: dict, scenario_id: str) -> dict:
    """Compare current vs snapshot, emit alerts on complaint spikes.

    Returns the alert summary so callers (UI demo trigger) can show it.
    """
    snapshots = _load_snapshots()
    previous = snapshots.get(scenario_id, {}).get("reviews", [])
    current = list(product_dict.get("seller", {}).get("reviews", []))

    new_reviews = _new_reviews(current, previous)
    counts = _tokens_in(new_reviews)

    triggered: list[dict] = []
    for keyword in _COMPLAINT_KEYWORDS:
        count = _count_complaint(counts, keyword)
        if count >= _THRESHOLD:
            subject = f"New complaint pattern: \"{keyword}\" ({count} mentions)"
            body = (
                f"Scenario: {scenario_id}\n"
                f"New complaint keyword detected: \"{keyword}\"\n"
                f"Frequency: {count} mentions in new reviews\n"
                f"Action: Generate a response card to draft a public reply."
            )
            print("=" * 60)
            print("Pixii Pulse Review Monitor Alert")
            print("-" * 60)
            print(body)
            print("=" * 60)
            send_alert(
                subject,
                body,
                kind="review",
                scenario_id=scenario_id,
                keyword=keyword,
                severity=min(10, count),
            )
            triggered.append({"keyword": keyword, "count": count})

    snapshots[scenario_id] = {"reviews": current}
    _save_snapshots(snapshots)

    return {
        "scenario_id": scenario_id,
        "new_review_count": len(new_reviews),
        "triggered": triggered,
    }


def demo_trigger() -> dict:
    """Simulate 5 new 'snaps easily' reviews on resistance_bands and run watcher."""
    scenario = load_scenario("resistance_bands")
    injected = [
        "This band snaps easily — be careful.",
        "Snaps easily after light use. Do not buy.",
        "Mine snaps easily during pulls.",
        "Snaps easily in the middle. Returned.",
        "Snaps easily even on the lightest setting.",
    ]
    scenario["seller"]["reviews"] = injected + scenario["seller"]["reviews"]

    # Wipe the old snapshot for this scenario so the injected reviews count as new.
    snapshots = _load_snapshots()
    snapshots["resistance_bands"] = {"reviews": []}
    _save_snapshots(snapshots)

    return watch_reviews(scenario, "resistance_bands")


if __name__ == "__main__":
    print(demo_trigger())
