"""SQLite history store for ORACLE.

Tracks every approved/denied action with timestamp, scenario, and category
so the History & Trends page can show stats and weekly charts.
"""
from __future__ import annotations

import sqlite3
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

_DB_PATH = Path(__file__).resolve().parent.parent / "oracle_history.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create all tables if they don't exist. Safe to call repeatedly."""
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS approved_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rank INTEGER,
                category TEXT,
                issue TEXT,
                output TEXT,
                oii INTEGER,
                scenario_id TEXT,
                timestamp TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS denied_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rank INTEGER,
                category TEXT,
                issue TEXT,
                oii INTEGER,
                scenario_id TEXT,
                timestamp TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL,
                scenario_id TEXT,
                subject TEXT,
                body TEXT,
                keyword TEXT,
                severity INTEGER DEFAULT 5,
                status TEXT DEFAULT 'new',
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        conn.commit()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def save_approved(
    rank: int,
    category: str,
    issue: str,
    output: str,
    oii: int,
    scenario_id: str,
) -> None:
    with _connect() as conn:
        conn.execute(
            """INSERT INTO approved_actions
               (rank, category, issue, output, oii, scenario_id, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (rank, category, issue, output, oii, scenario_id, _now_iso()),
        )
        conn.commit()


def save_denied(
    rank: int,
    category: str,
    issue: str,
    oii: int,
    scenario_id: str,
) -> None:
    with _connect() as conn:
        conn.execute(
            """INSERT INTO denied_actions
               (rank, category, issue, oii, scenario_id, timestamp)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (rank, category, issue, oii, scenario_id, _now_iso()),
        )
        conn.commit()


def get_history(limit: int = 50) -> list[dict]:
    """Last `limit` approved actions, newest first."""
    with _connect() as conn:
        rows = conn.execute(
            """SELECT id, rank, category, issue, output, oii, scenario_id, timestamp
               FROM approved_actions
               ORDER BY timestamp DESC, id DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_stats() -> dict:
    with _connect() as conn:
        approved_total = conn.execute(
            "SELECT COUNT(*) FROM approved_actions"
        ).fetchone()[0]
        denied_total = conn.execute(
            "SELECT COUNT(*) FROM denied_actions"
        ).fetchone()[0]

        cat_rows = conn.execute(
            "SELECT category, COUNT(*) AS c FROM approved_actions GROUP BY category"
        ).fetchall()
        by_category = {"listing": 0, "review": 0, "social": 0}
        for row in cat_rows:
            by_category[row["category"]] = row["c"]

        week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat(
            timespec="seconds"
        )
        this_week = conn.execute(
            "SELECT COUNT(*) FROM approved_actions WHERE timestamp >= ?",
            (week_ago,),
        ).fetchone()[0]

    return {
        "total_approved": approved_total,
        "total_denied": denied_total,
        "by_category": by_category,
        "this_week": this_week,
    }


def save_alert(
    kind: str,
    scenario_id: str | None,
    subject: str,
    body: str,
    keyword: str | None = None,
    severity: int = 5,
) -> int:
    """Insert a new alert row. Returns the new id."""
    now = _now_iso()
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO alerts
               (kind, scenario_id, subject, body, keyword, severity,
                status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, 'new', ?, ?)""",
            (kind, scenario_id, subject, body, keyword, int(severity), now, now),
        )
        conn.commit()
        return int(cur.lastrowid)


def get_pending_alerts(kind: str | None = None, limit: int = 30) -> list[dict]:
    """Alerts the seller hasn't acted on yet (status in {new, seen})."""
    sql = (
        "SELECT id, kind, scenario_id, subject, body, keyword, severity, "
        "status, created_at, updated_at FROM alerts "
        "WHERE status IN ('new', 'seen')"
    )
    args: list = []
    if kind:
        sql += " AND kind = ?"
        args.append(kind)
    sql += " ORDER BY created_at DESC LIMIT ?"
    args.append(int(limit))
    with _connect() as conn:
        rows = conn.execute(sql, args).fetchall()
        return [dict(r) for r in rows]


def get_pending_count(kind: str | None = None) -> int:
    sql = "SELECT COUNT(*) FROM alerts WHERE status IN ('new', 'seen')"
    args: list = []
    if kind:
        sql += " AND kind = ?"
        args.append(kind)
    with _connect() as conn:
        return int(conn.execute(sql, args).fetchone()[0])


def update_alert_status(alert_id: int, status: str) -> None:
    """Status transitions: new -> seen -> actioned/resolved (terminal)."""
    if status not in {"new", "seen", "actioned", "resolved"}:
        raise ValueError(f"invalid alert status: {status}")
    with _connect() as conn:
        conn.execute(
            "UPDATE alerts SET status = ?, updated_at = ? WHERE id = ?",
            (status, _now_iso(), int(alert_id)),
        )
        conn.commit()


def get_weekly_trend() -> list[dict]:
    """Last 7 days of approved/denied counts, oldest day first."""
    today = datetime.now(timezone.utc).date()
    days = [today - timedelta(days=i) for i in range(6, -1, -1)]

    with _connect() as conn:
        approved_rows = conn.execute(
            """SELECT DATE(timestamp) AS d, COUNT(*) AS c
               FROM approved_actions
               WHERE timestamp >= ?
               GROUP BY DATE(timestamp)""",
            ((today - timedelta(days=7)).isoformat(),),
        ).fetchall()
        denied_rows = conn.execute(
            """SELECT DATE(timestamp) AS d, COUNT(*) AS c
               FROM denied_actions
               WHERE timestamp >= ?
               GROUP BY DATE(timestamp)""",
            ((today - timedelta(days=7)).isoformat(),),
        ).fetchall()

    approved_map = {row["d"]: row["c"] for row in approved_rows}
    denied_map = {row["d"]: row["c"] for row in denied_rows}

    return [
        {
            "date": d.isoformat(),
            "approved": approved_map.get(d.isoformat(), 0),
            "denied": denied_map.get(d.isoformat(), 0),
        }
        for d in days
    ]
