"""Pixii Pulse — Streamlit UI.

Pages: Daily Actions (core), History & Trends, Review Monitor,
Competitor Monitor, Settings. Password-gated. Background scheduler runs
the daily pipeline at 8:00 AM.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

from main import run_pipeline_for_scenario
from scheduler import start_scheduler
from utils.db import (
    get_history,
    get_pending_alerts,
    get_pending_count,
    get_stats,
    get_weekly_trend,
    init_db,
    save_approved,
    save_denied,
    update_alert_status,
)
from utils.notifier import send_morning_briefing
from utils.pixii_simulator import (
    fmt_seller_header,
    get_skus,
    pick_priority_sku,
)

load_dotenv()

st.set_page_config(
    page_title="Pixii Pulse — Amazon Intelligence",
    page_icon="🔮",
    layout="wide",
    initial_sidebar_state="expanded",
)


# -----------------------------------------------------------------------------
# Theme polish — custom CSS injected once on every rerun
# -----------------------------------------------------------------------------
def _inject_theme() -> None:
    st.markdown(
        """
        <style>
          /* Background gradient on the main area */
          .stApp {
            background: radial-gradient(circle at 20% 0%, #1A1F3A 0%, #0B1221 60%);
          }

          /* Sidebar — branded gradient */
          [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #151E32 0%, #0B1221 100%);
            border-right: 1px solid rgba(139, 92, 246, 0.15);
          }
          [data-testid="stSidebar"] h1 {
            background: linear-gradient(135deg, #8B5CF6 0%, #EC4899 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            font-weight: 800;
            letter-spacing: -0.02em;
          }

          /* Big page titles get a subtle gradient too */
          .block-container h1 {
            font-weight: 800;
            letter-spacing: -0.02em;
          }

          /* Primary button — gradient + lift on hover */
          .stButton > button[kind="primary"] {
            background: linear-gradient(135deg, #6366F1 0%, #8B5CF6 60%, #EC4899 100%);
            border: none;
            color: white;
            font-weight: 600;
            padding: 0.6rem 1.4rem;
            border-radius: 10px;
            transition: transform 0.15s ease, box-shadow 0.15s ease;
            box-shadow: 0 2px 8px rgba(139, 92, 246, 0.25);
          }
          .stButton > button[kind="primary"]:hover {
            transform: translateY(-1px);
            box-shadow: 0 6px 20px rgba(139, 92, 246, 0.45);
          }

          /* Secondary button polish */
          .stButton > button:not([kind="primary"]) {
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 10px;
            font-weight: 500;
            transition: background 0.15s ease, border-color 0.15s ease;
          }
          .stButton > button:not([kind="primary"]):hover {
            background: rgba(139, 92, 246, 0.1);
            border-color: rgba(139, 92, 246, 0.4);
          }

          /* Metric blocks — bigger numbers, softer labels */
          [data-testid="stMetricValue"] {
            font-size: 2rem !important;
            font-weight: 700 !important;
            letter-spacing: -0.02em;
          }
          [data-testid="stMetricLabel"] {
            font-size: 0.78rem !important;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            opacity: 0.65;
            font-weight: 600;
          }

          /* Container borders — softer */
          [data-testid="stContainer"] > div:has(> [data-testid="stContainer"]) {
            border-radius: 14px;
          }

          /* Expander styling */
          [data-testid="stExpander"] details {
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 10px;
          }
          [data-testid="stExpander"] summary {
            font-weight: 600;
            padding: 0.7rem 1rem;
          }

          /* Progress bar — purple */
          [data-testid="stProgressBar"] > div > div {
            background: linear-gradient(90deg, #6366F1 0%, #8B5CF6 50%, #EC4899 100%) !important;
          }

          /* Pulse Score / category pill badges */
          .pp-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 999px;
            font-size: 0.72rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin-right: 8px;
          }
          .pp-badge-listing { background: rgba(59, 130, 246, 0.18); color: #93C5FD; border: 1px solid rgba(59, 130, 246, 0.4); }
          .pp-badge-review  { background: rgba(245, 158, 11, 0.18); color: #FCD34D; border: 1px solid rgba(245, 158, 11, 0.4); }
          .pp-badge-social  { background: rgba(16, 185, 129, 0.18); color: #6EE7B7; border: 1px solid rgba(16, 185, 129, 0.4); }
          .pp-badge-pricing { background: rgba(168, 85, 247, 0.18); color: #D8B4FE; border: 1px solid rgba(168, 85, 247, 0.4); }
          .pp-badge-approved { background: rgba(34, 197, 94, 0.18); color: #86EFAC; border: 1px solid rgba(34, 197, 94, 0.4); }

          /* Card-style container with subtle accent */
          [data-testid="stContainer"][class*="border"] {
            background: rgba(255, 255, 255, 0.02);
            border-color: rgba(255, 255, 255, 0.08) !important;
            backdrop-filter: blur(8px);
          }

          /* Brand wordmark for the login screen */
          .pp-wordmark {
            font-size: 3rem;
            font-weight: 900;
            letter-spacing: -0.04em;
            background: linear-gradient(135deg, #6366F1 0%, #8B5CF6 50%, #EC4899 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 0.2rem;
          }
          .pp-tagline {
            opacity: 0.7;
            font-size: 1.1rem;
            margin-bottom: 1.5rem;
          }

          /* Card priority header layout helper */
          .pp-card-header {
            display: flex;
            align-items: center;
            flex-wrap: wrap;
            gap: 8px;
            margin-bottom: 4px;
          }
          .pp-card-rank { font-size: 0.85rem; opacity: 0.7; font-weight: 600; }
          .pp-card-title { font-size: 1.15rem; font-weight: 700; letter-spacing: -0.01em; }
        </style>
        """,
        unsafe_allow_html=True,
    )


_inject_theme()

init_db()

if "scheduler_started" not in st.session_state:
    try:
        start_scheduler()
    except Exception as exc:
        print(f"[app] scheduler start failed: {exc}")
    st.session_state.scheduler_started = True


# -----------------------------------------------------------------------------
# Password gate
# -----------------------------------------------------------------------------
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        st.markdown(
            '<div class="pp-wordmark">Pixii Pulse</div>'
            '<div class="pp-tagline">Three Amazon decisions, already made. Approve or deny.</div>',
            unsafe_allow_html=True,
        )
        password = st.text_input("Enter access code", type="password")
        if st.button("Enter", type="primary", use_container_width=True):
            if password == os.getenv("APP_PASSWORD", "pixii2026"):
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Invalid access code")
    st.stop()


# -----------------------------------------------------------------------------
# Sidebar nav (with live alert badges)
# -----------------------------------------------------------------------------
NAV_PAGES = [
    "🎯 Daily Actions",
    "📊 History & Trends",
    "🔍 Review Monitor",
    "📡 Competitor Monitor",
    "⚙️ Settings",
]


def _decorate_nav() -> list[str]:
    review_n = get_pending_count("review")
    comp_n = get_pending_count("competitor")
    decorated = list(NAV_PAGES)
    if review_n > 0:
        decorated[2] = f"🔍 Review Monitor  ·  {review_n}"
    if comp_n > 0:
        decorated[3] = f"📡 Competitor Monitor  ·  {comp_n}"
    return decorated


def _canonical_page(label: str) -> str:
    for canonical in NAV_PAGES:
        if label.startswith(canonical):
            return canonical
    return label


st.sidebar.title("🔮 Pixii Pulse")
st.sidebar.markdown("Amazon Intelligence Platform")
st.sidebar.divider()

# Page is tracked in session_state.page (NOT the radio's key) so other parts
# of the app can navigate programmatically without colliding with Streamlit's
# "can't modify a widget key after instantiation" rule.
if "page" not in st.session_state:
    st.session_state.page = NAV_PAGES[0]

_decorated = _decorate_nav()
_canonical_options = [_canonical_page(o) for o in _decorated]
try:
    _current_idx = _canonical_options.index(st.session_state.page)
except ValueError:
    _current_idx = 0
    st.session_state.page = NAV_PAGES[0]

selected_label = st.sidebar.radio(
    "Navigate",
    _decorated,
    index=_current_idx,
)
_new_page = _canonical_page(selected_label)
if _new_page != st.session_state.page:
    # Manual click — sync our tracker.
    st.session_state.page = _new_page
page = st.session_state.page

def _category_pill(category: str) -> str:
    cat = (category or "").lower()
    label = cat.upper() if cat else "ACTION"
    return f'<span class="pp-badge pp-badge-{cat}">{label}</span>'


def _approved_pill() -> str:
    return '<span class="pp-badge pp-badge-approved">✓ Approved</span>'


# ---- Scenario_id → Pixii catalog SKU id ---------------------------------
def _sku_id_for_scenario(scenario_id: str) -> str | None:
    if not scenario_id:
        return None
    for sku in get_skus():
        if sku.get("scenario_id") == scenario_id:
            return sku.get("sku_id")
    return None


# ---- Pretty time-ago label for alerts ------------------------------------
def _time_ago(iso_ts: str) -> str:
    from datetime import datetime, timezone
    if not iso_ts:
        return ""
    try:
        ts = datetime.fromisoformat(iso_ts)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
    except ValueError:
        return iso_ts
    delta = datetime.now(timezone.utc) - ts
    secs = int(delta.total_seconds())
    if secs < 60:
        return "just now"
    if secs < 3600:
        return f"{secs // 60} min ago"
    if secs < 86400:
        return f"{secs // 3600}h ago"
    return f"{secs // 86400}d ago"


def _render_alert_card(alert: dict, ctx_prefix: str) -> None:
    """Render one alert with three action buttons. ctx_prefix scopes button keys."""
    pill = _category_pill("review" if alert["kind"] == "review" else "pricing")
    new_dot = "🔴 " if alert["status"] == "new" else ""
    sku_id = _sku_id_for_scenario(alert.get("scenario_id") or "") or alert.get(
        "scenario_id"
    ) or ""

    with st.container(border=True):
        st.markdown(
            f"""
            <div class="pp-card-header">
              {pill}
              <span class="pp-card-rank">{sku_id} · {_time_ago(alert.get("created_at",""))}</span>
            </div>
            <div class="pp-card-title">{new_dot}{alert.get("subject","")}</div>
            """,
            unsafe_allow_html=True,
        )
        body = (alert.get("body") or "").strip()
        if body:
            st.markdown(
                f"<div style='opacity:0.78;margin-top:8px;white-space:pre-wrap;'>"
                f"{body}</div>",
                unsafe_allow_html=True,
            )

        c1, c2, c3, _ = st.columns([1.4, 1, 1.2, 2])
        scenario_id = alert.get("scenario_id") or ""
        with c1:
            if st.button(
                "⚡ Generate response card",
                key=f"{ctx_prefix}_gen_{alert['id']}",
                type="primary",
            ):
                update_alert_status(alert["id"], "actioned")
                st.session_state.alert_focus_scenario = scenario_id
                st.session_state.page = NAV_PAGES[0]  # Daily Actions
                st.rerun()
        with c2:
            if st.button("💤 Snooze", key=f"{ctx_prefix}_snooze_{alert['id']}"):
                update_alert_status(alert["id"], "seen")
                st.rerun()
        with c3:
            if st.button(
                "✅ Mark resolved", key=f"{ctx_prefix}_resolve_{alert['id']}"
            ):
                update_alert_status(alert["id"], "resolved")
                st.rerun()
PROGRESS_STAGES = [
    "🔍 Scanning listings...",
    "🧠 Analysing gaps...",
    "📊 Deciding priorities...",
    "✍️ Preparing outputs...",
]


def _reset_run_state() -> None:
    st.session_state.pipeline_result = None
    st.session_state.card_states = {}


PROGRESS_STAGES_AGENTIC = [
    "🔍 Scanning listings...",
    "🤖 Investigator agent calling tools...",
    "🧠 Analysing gaps...",
    "📊 Deciding priorities...",
    "✍️ Preparing outputs...",
]


def _render_progress_then_run(run_fn, stages=None) -> dict:
    """Run pipeline with a progress bar. Returns the new dict shape."""
    stages = stages or PROGRESS_STAGES_AGENTIC
    progress_bar = st.progress(0)
    status_text = st.empty()
    step = max(1, 100 // len(stages))
    with st.spinner(""):
        for i, msg in enumerate(stages):
            status_text.text(msg)
            progress_bar.progress(min(100, (i + 1) * step))
        result = run_fn()
    progress_bar.empty()
    status_text.empty()
    return result


_TOOL_LABELS = {
    "fetch_competitor_listing": "Pulled a competitor's Amazon listing",
    "get_keyword_trend": "Checked Google Trends for keyword demand",
    "search_reddit_mentions": "Searched Reddit for outside-Amazon mentions",
}


def _humanise_tool_call(call: dict) -> str:
    """Turn a raw tool-call dict into a plain-English summary line."""
    tool = call.get("tool", "")
    args = call.get("args") or {}
    label = _TOOL_LABELS.get(tool, tool.replace("_", " ").capitalize())

    # Pick the most relevant argument value to show inline
    arg_hint = ""
    if "asin" in args:
        arg_hint = f" — competitor `{args['asin']}`"
    elif "keyword" in args:
        arg_hint = f" — *“{args['keyword']}”*"
    elif "query" in args:
        arg_hint = f" — *“{args['query']}”*"

    return f"{label}{arg_hint}"


def _render_investigation_panel(investigation: dict) -> None:
    """Plain-English summary of what the investigator agent did before recommending."""
    if not investigation:
        return
    tool_calls = investigation.get("tool_calls") or []
    notes = (investigation.get("research_notes") or "").strip()
    if not tool_calls and not notes:
        return

    with st.expander(
        f"🤖 Pixii Pulse looked at {len(tool_calls)} extra source(s) before recommending",
        expanded=True,
    ):
        if notes:
            st.markdown(f"**What Pixii Pulse found:** {notes}")
            st.divider()
        if tool_calls:
            st.markdown("**Where it looked:**")
            for i, call in enumerate(tool_calls, start=1):
                st.markdown(f"{i}. {_humanise_tool_call(call)}")
        st.caption(
            "Pixii Pulse decided which sources to check — Amazon listings, "
            "Google Trends, and Reddit — based on what it saw in your data."
        )


# =============================================================================
# 🎯 DAILY ACTIONS
# =============================================================================
if page == "🎯 Daily Actions":
    st.title("🎯 Today's Actions")
    st.caption(
        f"Logged in as **{fmt_seller_header()}**. "
        "Pixii Pulse pulls your catalog and competitive set from Pixii's database — "
        "no URLs to paste, no setup."
    )

    all_skus = get_skus()
    default_sku = pick_priority_sku()
    sku_options = [
        f"{s['sku_id']} — {s['title'][:60]} (priority {s['priority_score']})"
        for s in all_skus
    ]
    default_idx = next(
        (i for i, s in enumerate(all_skus) if s["sku_id"] == default_sku["sku_id"]),
        0,
    )

    # If a Monitor alert sent us here, pre-select the matching SKU.
    alert_focus_scenario = st.session_state.pop("alert_focus_scenario", None)
    if alert_focus_scenario:
        focus_sku_id = _sku_id_for_scenario(alert_focus_scenario)
        if focus_sku_id:
            for i, s in enumerate(all_skus):
                if s["sku_id"] == focus_sku_id:
                    default_idx = i
                    break
            st.info(
                f"Routed here from a Monitor alert — pre-selected **{focus_sku_id}**. "
                "Click *Generate Today's Briefing* to draft the response."
            )

    # Dropdown FIRST so the panel below can react to the selection.
    override_label = st.selectbox(
        "Today's focus (Pixii Pulse defaults to the highest-priority SKU — change if you want)",
        sku_options,
        index=default_idx,
    )
    selected_sku_id = override_label.split(" — ")[0]
    selected_sku = next(s for s in all_skus if s["sku_id"] == selected_sku_id)

    with st.expander(
        f"📌 Analysing **{selected_sku['sku_id']}**  "
        f"·  priority score {selected_sku['priority_score']}",
        expanded=True,
    ):
        st.write(f"**Why:** {selected_sku['priority_reason']}")
        c1, c2, c3 = st.columns(3)
        c1.metric(
            "Conversion (30d)",
            f"{selected_sku['conversion_rate_30d']}%",
            f"{selected_sku['conversion_rate_trend_pct']:+.1f}%",
        )
        c2.metric("Ad spend (30d)", f"${selected_sku['ad_spend_30d_usd']:,.0f}")
        c3.metric(
            "BSR change (7d)",
            f"{selected_sku['rank_change_7d']:+d}",
            delta_color="inverse",
        )

    scenario_id = selected_sku["scenario_id"]

    if st.button("⚡ Generate Today's Briefing", type="primary", use_container_width=True):
        _reset_run_state()
        try:
            with st.status(
                "Pulling your catalog from Pixii database...",
                expanded=False,
            ) as status:
                status.update(
                    label=f"Selected SKU: {selected_sku['sku_id']}  "
                    f"·  fetching competitive set...",
                    state="running",
                )
                result = _render_progress_then_run(
                    lambda: run_pipeline_for_scenario(scenario_id)
                )
                status.update(
                    label="Briefing prepared from Pixii data.",
                    state="complete",
                )

            st.session_state.current_scenario_id = scenario_id
            st.session_state.pipeline_result = result
            st.session_state.pipeline_cards = result.get("cards", [])
            st.session_state.pipeline_investigation = result.get("investigation", {})
        except Exception as exc:
            st.error(f"Pipeline failed: {exc}")

    if st.session_state.get("pipeline_result"):
        if "card_states" not in st.session_state:
            st.session_state.card_states = {}

        st.divider()

        _render_investigation_panel(
            st.session_state.get("pipeline_investigation") or {}
        )

        st.subheader("Your 3 Priorities")

        for item in st.session_state.get("pipeline_cards", []):
            rank = item["rank"]
            card_state = st.session_state.card_states.get(rank, "pending")

            if card_state == "denied":
                continue

            with st.container(border=True):
                col1, col2 = st.columns([3, 1])
                with col1:
                    approved_pill = _approved_pill() if card_state == "approved" else ""
                    st.markdown(
                        f"""
                        <div class="pp-card-header">
                          {_category_pill(item['category'])}
                          <span class="pp-card-rank">PRIORITY {rank}</span>
                          {approved_pill}
                        </div>
                        <div class="pp-card-title">{item['issue']}</div>
                        """,
                        unsafe_allow_html=True,
                    )
                with col2:
                    st.metric("Pulse Score", item["oii"])

                oii_pct = min(100, int((item["oii"] / 1000) * 100))
                st.progress(oii_pct)

                st.text_area(
                    "Ready-to-use output",
                    value=item["output"],
                    height=140,
                    key=f"output_{rank}",
                )

                with st.expander("Why this priority?"):
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Severity", item["severity"])
                    c2.metric("Frequency", item["frequency"])
                    c3.metric("Revenue Impact", item["revenue_impact"])
                    c4.metric("Pulse Score", item["oii"])
                    st.caption("Pulse Score = Severity × Frequency × Revenue Impact")

                with st.expander("📡 Publishing — what happens when you click OK"):
                    if item["category"] == "listing":
                        st.info(
                            "Clicking OK will push this rewritten bullet to your "
                            "Amazon listing via SP-API. Live in approximately 10 minutes."
                        )
                    elif item["category"] == "review":
                        st.info(
                            "Clicking OK will post this reply publicly on Amazon "
                            "under your seller account."
                        )
                    elif item["category"] == "social":
                        st.info(
                            "Clicking OK will schedule this caption to Instagram "
                            "tomorrow at 9:00 AM via the Meta Graph API."
                        )
                    elif item["category"] == "pricing":
                        st.info(
                            "Clicking OK will adjust this marketplace price "
                            "via Amazon SP-API. Live within 15 minutes."
                        )
                    st.caption(
                        "⚠️ In this prototype, OK logs to the history database. "
                        "Full SP-API and Meta API integration available in production."
                    )

                if card_state != "approved":
                    btn_col1, btn_col2, _ = st.columns([1, 1, 3])
                    with btn_col1:
                        if st.button("✅ OK", key=f"ok_{rank}", type="primary"):
                            save_approved(
                                rank=rank,
                                category=item["category"],
                                issue=item["issue"],
                                output=item["output"],
                                oii=item["oii"],
                                scenario_id=st.session_state.get(
                                    "current_scenario_id", "unknown"
                                ),
                            )
                            st.session_state.card_states[rank] = "approved"
                            st.rerun()
                    with btn_col2:
                        if st.button("❌ Deny", key=f"deny_{rank}"):
                            save_denied(
                                rank=rank,
                                category=item["category"],
                                issue=item["issue"],
                                oii=item["oii"],
                                scenario_id=st.session_state.get(
                                    "current_scenario_id", "unknown"
                                ),
                            )
                            st.session_state.card_states[rank] = "denied"
                            st.rerun()

        approved_count = sum(
            1 for s in st.session_state.card_states.values() if s == "approved"
        )
        if approved_count == 3:
            st.success("🎉 All 3 actions approved. Your daily Pixii Pulse briefing is complete.")
            if st.button("📋 Log briefing to console"):
                send_morning_briefing(st.session_state.get("pipeline_cards", []))
                st.success("Briefing logged. (Internal-only — no external apps used.)")


# =============================================================================
# 📊 HISTORY & TRENDS
# =============================================================================
elif page == "📊 History & Trends":
    st.title("📊 History & Trends")

    stats = get_stats()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Approved", stats["total_approved"])
    c2.metric("Total Denied", stats["total_denied"])
    c3.metric("This Week", stats["this_week"])
    total_decided = max(1, stats["total_approved"] + stats["total_denied"])
    approval_rate = int((stats["total_approved"] / total_decided) * 100)
    c4.metric("Approval Rate", f"{approval_rate}%")

    st.divider()

    trend = get_weekly_trend()
    if trend:
        dates = [t["date"] for t in trend]
        approved = [t["approved"] for t in trend]
        denied = [t["denied"] for t in trend]
        fig = go.Figure()
        fig.add_trace(go.Bar(name="Approved", x=dates, y=approved, marker_color="#00CC44"))
        fig.add_trace(go.Bar(name="Denied", x=dates, y=denied, marker_color="#FF4444"))
        fig.update_layout(barmode="group", title="7-Day Action History", height=320)
        st.plotly_chart(fig, use_container_width=True)

    cat = stats["by_category"]
    if sum(cat.values()) > 0:
        fig2 = px.pie(
            values=list(cat.values()),
            names=list(cat.keys()),
            title="Actions by Category",
            hole=0.4,
        )
        st.plotly_chart(fig2, use_container_width=True)

    st.subheader("Recent Approved Actions")
    history = get_history(limit=20)
    if history:
        df = pd.DataFrame(history)
        st.dataframe(
            df[["timestamp", "category", "issue", "oii", "scenario_id"]],
            use_container_width=True,
        )
    else:
        st.info(
            "No approved actions yet. Run your first analysis on the Daily Actions page."
        )


# =============================================================================
# 🔍 REVIEW MONITOR
# =============================================================================
elif page == "🔍 Review Monitor":
    st.title("🔍 Review Monitor")
    st.info(
        "Pixii Pulse monitors your reviews daily. New complaint patterns "
        "appear here as alerts you can act on with one click."
    )

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Monitoring Status", "Active ✅")
        st.metric("Check Frequency", "Daily at 8:00 AM")
    with col2:
        st.metric("Complaint Keywords Tracked", "15")
        st.metric("Alert Threshold", "3+ mentions")

    pending = get_pending_alerts(kind="review", limit=20)
    st.divider()

    if pending:
        st.subheader(f"Pending alerts · {len(pending)}")
        for alert in pending:
            _render_alert_card(alert, ctx_prefix="rev")
    else:
        st.subheader("Pending alerts · 0")
        st.caption("No new complaint patterns to act on. You're all clear.")

    st.divider()
    with st.expander("Live demo — simulate new reviews"):
        st.write(
            "Click below to inject 5 new reviews all mentioning "
            "*'snaps easily'* on the Resistance Bands product. The watcher will "
            "detect the spike and post a fresh alert above."
        )
        if st.button("🚨 Trigger Demo Alert", type="primary", key="rev_demo"):
            from review_watcher import demo_trigger
            with st.spinner("Running review watcher..."):
                demo_trigger()
            st.success("Alert posted. Scroll up to see it.")
            st.rerun()


# =============================================================================
# 📡 COMPETITOR MONITOR
# =============================================================================
elif page == "📡 Competitor Monitor":
    st.title("📡 Competitor Monitor")
    st.info(
        "Pixii Pulse watches competitor listings daily. Price drops, new "
        "keywords, and rating drops appear here as alerts you can act on with "
        "one click."
    )

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Monitoring Status", "Active ✅")
        st.metric("Check Frequency", "Daily at 8:00 AM")
    with col2:
        st.metric("Change Types Tracked", "3")
        st.caption("Price drops · new keywords · rating drops")

    pending = get_pending_alerts(kind="competitor", limit=20)
    st.divider()

    if pending:
        st.subheader(f"Pending alerts · {len(pending)}")
        for alert in pending:
            _render_alert_card(alert, ctx_prefix="cmp")
    else:
        st.subheader("Pending alerts · 0")
        st.caption("No competitor changes to act on. You're all clear.")

    st.divider()
    with st.expander("Live demo — simulate a competitor price drop"):
        st.write(
            "Click below to simulate a competitor dropping their price by 15% "
            "overnight. The monitor will detect the change and post a fresh "
            "alert above."
        )
        if st.button("📉 Trigger Price Drop Alert", type="primary", key="cmp_demo"):
            from competitor_monitor import demo_trigger
            with st.spinner("Running competitor monitor..."):
                demo_trigger()
            st.success("Alert posted. Scroll up to see it.")
            st.rerun()


# =============================================================================
# ⚙️ SETTINGS
# =============================================================================
elif page == "⚙️ Settings":
    st.title("⚙️ Settings")

    st.subheader("Scheduler")
    st.write("Daily Pixii Pulse run is scheduled for 8:00 AM every day.")
    if st.button("▶️ Run Now (Manual Trigger)"):
        from scheduler import daily_oracle_run
        with st.spinner("Running daily analysis..."):
            daily_oracle_run()
        st.success("Daily run complete. Briefing logged to the console.")

    st.divider()

    st.subheader("Reset")
    if "confirm_clear" not in st.session_state:
        st.session_state.confirm_clear = False

    if not st.session_state.confirm_clear:
        if st.button("🗑️ Clear History", type="secondary"):
            st.session_state.confirm_clear = True
            st.rerun()
    else:
        st.warning(
            "This will clear all approved/denied action history. This cannot be undone."
        )
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("Confirm Clear", type="primary"):
                db_path = Path(__file__).resolve().parent / "oracle_history.db"
                conn = sqlite3.connect(str(db_path))
                conn.execute("DELETE FROM approved_actions")
                conn.execute("DELETE FROM denied_actions")
                conn.commit()
                conn.close()
                st.session_state.confirm_clear = False
                st.success("History cleared.")
                st.rerun()
        with col_b:
            if st.button("Cancel"):
                st.session_state.confirm_clear = False
                st.rerun()
