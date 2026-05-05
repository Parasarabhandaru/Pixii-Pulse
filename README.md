# Pixii Pulse — Amazon Intelligence Platform

One-line summary: wake-up and ready-to-approve actions, already written.

## External APIs and tools (beyond the LLM)

Pixii Pulse satisfies the "2+ APIs or tools" rule with **four real external integrations**, three of which are wrapped as agent tools the LLM decides to call:

| Integration | What it does | Agent tool? |
| --- | --- | --- |
| **Amazon (HTTP scrape)** | Fetch a specific competitor's live listing on demand | ✅ `fetch_competitor_listing` |
| **Google Trends (pytrends)** | Validate real search demand for missing keywords (0–100 + trend) | ✅ `get_keyword_trend` |
| **Reddit (public JSON)** | Search outside-Amazon brand mentions and sentiment | ✅ `search_reddit_mentions` |
| **Open Exchange Rates** (`open.er-api.com`) | Convert local marketplace prices to USD-equivalent — drives the **International Pricing** card | (consumed by analyst) |

The agent loop (Groq function-calling) lives in [agents/investigator.py](agents/investigator.py) and runs as Step 2.5 of the pipeline. It receives the seller's product + the missing-keywords list + the priority reason, then **decides** which of the three tools to invoke, in what order. The trace is rendered in the UI above the 3 priority cards.

The pricing-opportunity finding ([agents/analyst.py](agents/analyst.py)) calls the FX API directly — it's a deterministic check, not an LLM decision — and produces a 4th card category: `pricing`.

**No external apps required from the seller.** No Slack, no email, no third-party platforms to install. Briefings and monitor alerts surface inside Pixii Pulse's UI and the local console.

## Setup

1. Clone or download this project.
2. Install dependencies: `pip install -r requirements.txt`
3. Add your API key to `.env`: `GROQ_API_KEY=your_key_here` (free at https://console.groq.com/keys).
4. Run: `streamlit run app.py`
5. Open http://localhost:8501
6. Enter access code: `pixii2026`

## Demo

Select **Demo Mode** on the Daily Actions page. Choose any of the 6 pre-built scenarios.
Click Run Analysis. Review the 3 priority cards. Click OK or Deny.

No live Amazon URLs needed for the demo.

## Pages

| Page | What it does |
| --- | --- |
| 🎯 Daily Actions | Paste URLs (or pick a scenario) → 3 priority cards with approve/deny |
| 📊 History & Trends | SQLite-backed approval log, weekly bar chart, category donut |
| 🔍 Review Monitor | Daily complaint-pattern detection. Demo button injects 5 fake reviews and fires an alert |
| 📡 Competitor Monitor | Price/keyword/rating change detection. Demo button injects a 15% price drop |
| ⚙️ Settings | Manual scheduler trigger, email config, cost tracking, history reset |

## Architecture

```
scanner.py → investigator.py (agentic, 2 tools) → analyst.py → decider.py → executor.py → app.py
```

Each agent is independent and testable. The pipeline passes a single Python dict between agents.

```
oracle/
├── app.py                    # Streamlit multi-page UI (password-gated)
├── main.py                   # run_pipeline + run_pipeline_for_scenario + token_cost_summary
├── scheduler.py              # APScheduler — daily 8:00 AM run + briefing email
├── review_watcher.py         # Detects new complaint patterns + demo_trigger
├── competitor_monitor.py     # Detects price/keyword/rating changes + demo_trigger
├── agents/
│   ├── scanner.py            # Live scrape with sample-data fallback + load_scenario
│   ├── tools.py              # 2 LLM-callable tools: fetch_competitor_listing + get_keyword_trend
│   ├── investigator.py       # Agentic Groq function-calling loop — picks tools to call
│   ├── analyst.py            # Keyword gap (Python) + sentiment + hook (Groq)
│   ├── decider.py            # Impact-Score ranking → top 3 with category mapping
│   └── executor.py           # One Groq call per priority + token tracking
├── utils/
│   ├── scraper.py            # BeautifulSoup Amazon scraper
│   ├── prompts.py            # All 5 LLM prompt templates
│   ├── claude_client.py      # Groq SDK wrapper + JSON extractor + token usage
│   ├── db.py                 # SQLite history (approved_actions + denied_actions)
│   └── notifier.py           # Slack webhook + console fallback
└── data/
    ├── sample_data.json          # 6 scenarios (yoga_mat, protein_powder, …)
    ├── review_snapshots.json     # auto-created by review_watcher
    └── competitor_snapshots.json # auto-created by competitor_monitor
```

## Gap Coverage

| Gap | Status |
| --- | --- |
| Data without decisions | ✅ Impact Score engine |
| Insights without outputs | ✅ LLM writes all content |
| No publishing | ✅ Simulated with SP-API / Meta API panels |
| No daily habit | ✅ APScheduler + email briefing |
| Reactive reviews | ✅ review_watcher.py with demo_trigger |
| Competitor blindness | ✅ competitor_monitor.py with demo_trigger |
| No history | ✅ SQLite history + Plotly trend charts |
| No cost visibility | ✅ Per-call token counter, displayed in UI |

## Notes on this build

- LLM provider is **Groq** (not Anthropic) — runs on the free tier with `llama-3.3-70b-versatile`.
  Function names in `utils/claude_client.py` are kept (`call_claude`, `call_claude_json`,
  `call_with_tokens`) so swapping providers later requires editing one file.
- SendGrid is optional. Without `SENDGRID_API_KEY`, every email prints to the console instead.
  The demo flow works without configuring SendGrid at all.
- Scheduler starts in the background when `app.py` boots. Trigger it manually from the Settings page.

## Test order

```bash
# 1. Sample data round-trips
python -c "from agents.scanner import load_scenario; print(load_scenario('yoga_mat')['scenario_id'])"

# 2. DB initialises cleanly
python -c "from utils.db import init_db; init_db(); print('DB OK')"

# 3. Full pipeline on one scenario
python main.py

# 4. Review watcher demo
python review_watcher.py

# 5. Competitor monitor demo
python competitor_monitor.py

# 6. UI
streamlit run app.py
```
