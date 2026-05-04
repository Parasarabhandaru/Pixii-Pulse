"""DECIDE agent — Step 4 in the ORACLE pipeline.

Takes the findings list from analyst.analyse() and returns EXACTLY 3
priorities, ranked by Oracle Impact Index (OII).

OII = severity * frequency * revenue_impact
"""
from __future__ import annotations

import copy

_TYPE_TO_CATEGORY = {
    "keyword_gap": "listing",
    "review_complaint": "review",
    "weak_hook": "social",
    "pricing_opportunity": "pricing",
}


def _oii(finding: dict) -> int:
    return (
        int(finding.get("severity", 0))
        * int(finding.get("frequency", 0))
        * int(finding.get("revenue_impact", 0))
    )


def _map_category(finding_type: str) -> str:
    return _TYPE_TO_CATEGORY.get(finding_type, "listing")


def decide(findings: list[dict]) -> list[dict]:
    """Return exactly 3 ranked priority objects.

    Each priority preserves finding["data"] so the executor has all the
    inputs it needs (keywords, complaint, gap_reason, etc.).
    """
    if not findings:
        raise ValueError("decide() requires at least one finding")

    enriched: list[dict] = []
    for finding in findings:
        item = {
            "type": finding["type"],
            "description": finding["description"],
            "oii": _oii(finding),
            "severity": int(finding.get("severity", 0)),
            "frequency": int(finding.get("frequency", 0)),
            "revenue_impact": int(finding.get("revenue_impact", 0)),
            "category": _map_category(finding["type"]),
            "data": copy.deepcopy(finding.get("data", {})),
        }
        enriched.append(item)

    enriched.sort(key=lambda f: f["oii"], reverse=True)

    # Pad to exactly 3 by duplicating the lowest-scored finding (with a
    # tiny OII decay so the cards remain visually distinct).
    while len(enriched) < 3:
        filler = copy.deepcopy(enriched[-1])
        filler["oii"] = max(1, filler["oii"] - 1)
        filler["description"] = filler["description"] + " (secondary)"
        enriched.append(filler)

    top3 = enriched[:3]
    for rank, item in enumerate(top3, start=1):
        item["rank"] = rank
    return top3
