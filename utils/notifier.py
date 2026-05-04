"""Internal notifier — persists alerts in the SQLite DB and prints to console.

Alerts are stored so the Pixii Pulse UI can render them as cards on the Review
Monitor and Competitor Monitor pages, with a sidebar count badge. No external
apps (Slack, email) — everything stays inside the platform.

Function names (`send_morning_briefing`, `send_alert`) are kept so existing
callers don't need to change.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from .db import save_alert


def _border() -> None:
    print("=" * 72)


def send_morning_briefing(actions: list) -> None:
    """Log the 3-card briefing to the console. Never raises."""
    today = datetime.now().strftime("%A, %B %d, %Y")
    _border()
    print(f"[pixii-pulse] Daily briefing — {today}")
    _border()
    if not actions:
        print("(no actions)")
    for item in actions:
        rank = item.get("rank", "?")
        category = (item.get("category") or "").upper()
        oii = item.get("oii", "?")
        issue = (item.get("issue") or "").strip()
        output = (item.get("output") or "").strip()
        print(f"\nPriority {rank} — {category} (Pulse {oii})")
        print(f"  Issue : {issue}")
        if output:
            preview = output if len(output) <= 320 else output[:317] + "..."
            print(f"  Output: {preview}")
    _border()
    print("Open Pixii Pulse → http://localhost:8501")
    _border()


def send_alert(
    subject: str,
    body: str,
    *,
    kind: str = "general",
    scenario_id: Optional[str] = None,
    keyword: Optional[str] = None,
    severity: int = 5,
) -> int:
    """Persist an alert in the DB so the UI can render it. Also print to console.

    Returns the new alert id (or 0 if persisting failed).
    """
    _border()
    print(f"[pixii-pulse alert] {subject}")
    print("-" * 72)
    print(body)
    _border()

    try:
        return save_alert(
            kind=kind,
            scenario_id=scenario_id,
            subject=subject,
            body=body,
            keyword=keyword,
            severity=severity,
        )
    except Exception as exc:
        print(f"[pixii-pulse alert] persist failed: {exc}")
        return 0
