# Pixii Pulse — Complete Walkthrough

End-to-end explanation of the project: what each click does, what each file does, how data flows between them, and why the architecture looks the way it does. Written so a reviewer (or future-you) can read it cold and understand everything in one pass.

Every technical term is explained inline (in parentheses) the first time it appears. There is no separate glossary at the bottom — the meaning is right next to the term.

---

## 1. What Pixii Pulse is

Pixii Pulse is an Amazon-listing intelligence feature designed to live inside Pixii.AI's seller platform. It gives the seller exactly **three** approve-or-deny actions per day. No dashboards, no charts, no decisions to make — just three cards saying *"do this, here's the text, click OK or Deny."*

The product thesis: every other Amazon tool gives the seller data and asks them to decide what to do. Pixii Pulse gives the seller decisions (already made) and content (already written). The seller's only job is to approve or reject.

In production, Pixii Pulse runs inside Pixii. It reads the seller's catalog (their product list) and competitive set (the rival listings Pixii has identified) directly from Pixii's database. The seller never pastes a URL; the form for that doesn't exist in the production UI. This prototype simulates Pixii's database with a JSON file ([data/pixii_catalog.json](data/pixii_catalog.json)).

---

## 2. The whole user experience, click by click

### 2.1 Launching the app

```powershell
streamlit run app.py
```

Streamlit (a Python framework that turns Python scripts into web UIs) starts a local web server, typically at `http://localhost:8501`.

### 2.2 The login screen

The first screen is a password gate. The seller types `pixii2026` (configured in [.env](.env) as `APP_PASSWORD`) and clicks **Enter**. The check happens in [app.py](app.py) using `os.getenv("APP_PASSWORD")` — no real auth provider is used; this is a stand-in for Pixii's actual SSO (Single Sign-On, the corporate authentication system that proves who you are once and lets you into many apps).

Once authenticated, `st.session_state.authenticated = True` and the rest of the app loads. `st.session_state` is Streamlit's per-browser-tab dict (a key-value store that persists across UI interactions in one session) used to remember things between reruns. Streamlit reruns the entire script on every interaction, so anything that should persist must live in `st.session_state`.

### 2.3 The sidebar

Five pages, listed as a radio button (a pick-one widget) in the left sidebar:

- 🎯 **Daily Actions** — the core product
- 📊 **History & Trends** — past approvals/denials with charts
- 🔍 **Review Monitor** — daily complaint-pattern detection
- 📡 **Competitor Monitor** — daily price/keyword/rating change detection
- ⚙️ **Settings** — manual triggers, cost tracking, history reset

### 2.4 The Daily Actions page (top to bottom)

**Header.** A line saying *"Logged in as PrimeBrands Co. (Pixii ID: PB-00417). Pixii Pulse pulls your catalog and competitive set from Pixii's database — no URLs to paste, no setup."*

That single line is the entire pitch. It says: *the seller doesn't operate this tool; the tool operates on data the platform already has*.

**Pixii's auto-pick panel.** A boxed expander (a collapsible section in Streamlit) that defaults to open. It shows:

- The chosen SKU (Stock Keeping Unit, the unique product identifier the seller uses internally — e.g. `PB-RES-05` for "PrimeBrands Resistance bands #5")
- The **priority score** (a 0–100 number representing how urgently this SKU needs attention, calculated from conversion-rate trend, ad-spend efficiency, and BSR change)
- The **priority reason** (a one-sentence explanation of why this SKU was picked, written in plain English by Pixii's recommendation engine — for the prototype, baked into the catalog JSON)
- Three metrics: Conversion rate (the percentage of visitors who buy, key Amazon health signal), Ad spend over 30 days, and BSR change (Best Sellers Rank, Amazon's category ranking — lower number = better, so a *negative* change like -64 means the product fell 64 spots, which is bad)

Pixii Pulse picks the SKU with the highest priority score. The function is `pick_priority_sku()` in [utils/pixii_simulator.py](utils/pixii_simulator.py), which simulates what Pixii's real recommendation engine would surface.

**The override dropdown.** Inside the same panel, a `st.selectbox` (a dropdown widget) labelled *"Analysing this SKU (change to focus on a different one)"* lets the seller switch to a different product. Useful for sellers managing many SKUs who want to look ahead. This is not a "demo mode" — it's a normal product control.

**The Generate button.** A single primary-styled button: **⚡ Generate Today's Briefing**. Clicking it triggers `run_pipeline_for_scenario(scenario_id)` from [main.py](main.py), wrapped in a Streamlit `st.status` block (a progress widget that shows a spinner with stage labels). The pipeline takes 4–10 seconds end to end.

**Cost line.** A small caption appears under the button after the run: *"Analysis cost: $0.0022 (740 tokens)"*. Tokens are the unit LLMs (Large Language Models, the AI models that generate text — Pixii Pulse uses Groq's `llama-3.3-70b-versatile`) bill in. Roughly 0.75 words per token. The dollar figure is what an equivalent paid model would have cost; on Groq's free tier the actual cost is $0.

### 2.5 The investigator panel

Right after the cost line, an expander appears titled *"🤖 Investigator agent — called N tool(s) before recommending"*. Inside:

- **Research notes** — a 2-3 sentence paragraph the LLM wrote after running its tools. It summarizes what it learned about the seller's listing relative to competitors and search demand.
- **Tool-call trace** — a list of every tool the LLM invoked, with arguments and a snippet of what the tool returned. Each line looks like:

  ```
  iter 1 — fetch_competitor_listing(asin='B0PWHEY9911') → {'source': 'sample_fallback', 'asin': ...}
  ```

  - `iter 1` means iteration 1 of the agent loop (the LLM can run multiple rounds of tool calls)
  - `fetch_competitor_listing(asin='B0PWHEY9911')` is the function the LLM chose to call, with the ASIN (Amazon Standard Identification Number, the 10-character ID Amazon assigns to every product) it wanted to look up
  - The arrow points to a preview of the tool's return value

This panel is **the proof that Pixii Pulse is agentic** (the LLM is making decisions about what to do, not just executing a fixed pipeline). The reviewer can see the model picking tools and the reasoning fold into the cards below.

### 2.6 The three priority cards

Below the investigator panel, exactly three boxed cards appear. Each has:

1. **Header:** a coloured square emoji indicating category (🟦 listing, 🟨 review, 🟩 social, 🟪 pricing) plus *"Priority N — CATEGORY"* plus an *"✅ APPROVED"* tag once the OK button is clicked
2. **Issue line:** one sentence saying what the problem is
3. **Impact Score metric:** Pixii Pulse's priority score for this finding, computed as severity × frequency × revenue_impact — each component is a 1–10 integer, so the score ranges 0–1000
4. **Progress bar:** a visual representation of the Impact Score as a percentage of 1000
5. **Ready-to-use output:** the actual text the seller will publish or post — a rewritten bullet for listing, a public reply for review, an Instagram caption for social, a price-change recommendation for pricing
6. **"Why this priority?" expander:** a breakdown of the Impact Score into Severity (1–10, how bad the issue is), Frequency (1–10, how often it manifests), and Revenue Impact (1–10, how much revenue this affects). Click to audit Pixii Pulse's reasoning.
7. **"📡 Publishing" expander:** describes what would happen in production if the seller clicked OK — for example, *"Clicking OK will push this rewritten bullet to your Amazon listing via SP-API"* (SP-API is Amazon's Selling Partner API, the official seller-account API for editing listings, posting replies, and managing inventory)
8. **OK / Deny buttons:** primary green for OK, secondary red for Deny

OK saves the action to a SQLite database (a lightweight, file-based relational database — the entire database is one file called `oracle_history.db` next to the app) via `save_approved()`. Deny saves only metadata via `save_denied()` so we can track approval rates. Both update `st.session_state.card_states` so the card hides or shows the approved badge on the next rerun.

### 2.7 After all three are approved

A success banner appears: *"🎉 All 3 actions approved. Your daily Pixii Pulse briefing is complete."* and a button **📋 Log briefing to console** lets the seller print the full briefing to the terminal. There are no external integrations (no Slack, no email) — keeping the feature self-contained inside Pixii.

### 2.8 Other pages

**📊 History & Trends.** Reads from the SQLite database to render: four metrics at the top (total approved, total denied, this-week count, approval rate), a 7-day Plotly bar chart (Plotly is a Python charting library that produces interactive HTML charts) of approvals vs denials per day, a category donut (a chart that shows what proportion of approvals were listing vs review vs social vs pricing), and a recent-actions table.

**🔍 Review Monitor.** Shows the monitoring status (active, daily 8 AM, 15 keywords tracked, threshold 3+ mentions) and a *"Trigger Demo Alert"* button. Clicking it injects 5 fake reviews mentioning *"snaps easily"* on the resistance-bands SKU and runs the watcher, which detects the spike and prints an alert.

**📡 Competitor Monitor.** Same shape as Review Monitor. Demo button simulates a competitor dropping their price 15% overnight; the monitor detects the change and fires an alert.

**⚙️ Settings.** Manual *"Run Now"* trigger for the daily scheduler, a notifications notice (explaining Pixii Pulse keeps everything inside the platform), per-run cost display (always *Free (Groq)* on the current tier), and a Clear History button (with a two-step confirm to prevent accidents).

---

## 3. The pipeline architecture

Here is the full data flow, with each box's input and output:

```
┌─────────────────────────────────────────────────────────────┐
│  app.py — Streamlit UI                                       │
│  user clicks "Generate" with a chosen scenario_id            │
└──────────────────────────┬──────────────────────────────────┘
                           │ scenario_id (e.g., "yoga_mat")
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  main.run_pipeline_for_scenario(scenario_id)                 │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  agents/scanner.load_scenario(scenario_id)                   │
│  reads sample_data.json + pixii_catalog.json                 │
│  returns: {seller, competitors, scenario_id}                 │
└──────────────────────────┬──────────────────────────────────┘
                           │ scan_data
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  agents/investigator.investigate(scan_data, sku_context)     │
│  ┌─ Groq function-calling loop ──────────────────────────┐   │
│  │ The LLM picks from 3 tools:                          │   │
│  │  • fetch_competitor_listing(asin)  → Amazon HTTP     │   │
│  │  • get_keyword_trend(keyword)      → Google Trends    │   │
│  │  • search_reddit_mentions(query)   → Reddit JSON     │   │
│  │ Loops until done or hits 4 iterations / 5 tool calls │   │
│  └──────────────────────────────────────────────────────┘   │
│  returns: {research_notes, tool_calls, raw_results}          │
└──────────────────────────┬──────────────────────────────────┘
                           │ investigation
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  agents/analyst.analyse(scan_data)                           │
│  runs four finding generators:                               │
│   1. _keyword_gap         (pure Python token diff)           │
│   2. _sentiment           (Groq LLM call on reviews)         │
│   3. _hook                (Groq LLM call on titles)          │
│   4. _pricing_opportunity (Open Exchange Rates HTTP API)     │
│  returns: list of 1–4 findings                               │
└──────────────────────────┬──────────────────────────────────┘
                           │ findings
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  agents/decider.decide(findings)                             │
│  computes Impact Score = severity × frequency × revenue_impact        │
│  sorts descending, takes top 3 (pads if fewer)               │
│  maps finding type → category (listing/review/social/pricing)│
│  returns: exactly 3 priorities, ranked                       │
└──────────────────────────┬──────────────────────────────────┘
                           │ priorities (3 items)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  agents/executor.execute(priorities, scan_data)              │
│  for each priority, dispatch by category:                    │
│   • listing  → LISTING_REWRITE_PROMPT  → rewritten bullet    │
│   • review   → REVIEW_REPLY_PROMPT     → public reply        │
│   • social   → SOCIAL_PROMPT           → IG caption          │
│   • pricing  → PRICING_REWRITE_PROMPT  → price recommendation│
│  each is one Groq LLM call; tracks token usage               │
│  returns: 3 final cards with output text                     │
└──────────────────────────┬──────────────────────────────────┘
                           │ {cards, investigation, scenario_id}
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  app.py — render the 3 cards + investigation panel           │
│  user clicks OK or Deny on each                              │
│  → save_approved() / save_denied() write to SQLite           │
└─────────────────────────────────────────────────────────────┘
```

### 3.1 The five stages, in plain English

1. **SCAN.** Fetch the seller's product and the competitors. In production, Pixii's database supplies them. In the prototype, they come from `sample_data.json`.
2. **INVESTIGATE (agentic).** Hand the raw data to the LLM and let it decide what extra context to gather using three tools. Returns a brief written summary plus a tool-call trace.
3. **ANALYSE.** Run four detection routines that produce structured findings. Some are pure Python (keyword gap), some call the LLM directly (sentiment, hook), one calls a third-party API (FX rates for pricing).
4. **DECIDE.** Score every finding with the Impact Score formula and pick the top three. Always returns exactly three.
5. **EXECUTE.** For each of the three priorities, call the LLM once with the right prompt to produce the seller's copy-paste-ready output.

---

## 4. File-by-file walkthrough

### 4.1 [app.py](app.py)

The Streamlit UI. ~470 lines. Imports the pipeline functions from `main.py`, the database helpers from `utils/db.py`, the catalog helpers from `utils/pixii_simulator.py`, and the notifier from `utils/notifier.py`. Top-level structure:

1. Page config and `init_db()` (creates SQLite tables if missing)
2. Background scheduler start (daily 8 AM job, see section 4.7)
3. Password gate (blocks all rendering if not authenticated)
4. Sidebar with five-page radio
5. Branch on `page` value — one block per page

The Daily Actions block is the longest: it renders the auto-pick panel, the override dropdown, the Generate button, and (after a successful run) the investigator panel and three priority cards. State lives in `st.session_state` keys: `pipeline_result`, `pipeline_cards`, `pipeline_investigation`, `card_states`, `current_scenario_id`.

### 4.2 [main.py](main.py)

The pipeline orchestrator. Three public functions:

- `run_pipeline(urls)` — live mode (scrapes URLs, falls back to sample data on failure). Not used by the UI any more but kept for backward compatibility with `python main.py` testing.
- `run_pipeline_for_scenario(scenario_id)` — demo/Pixii-mode. Loads a sample scenario by ID, looks up the matching SKU context in the catalog, then runs `_run`.
- `token_cost_summary(payload)` — sums `tokens_used` across the cards and returns a display-ready cost string.

`_run(scan_data, sku_context)` is the shared pipeline body that calls investigator → analyst → decider → executor. It attaches `sku_context` to `scan_data` so downstream agents (specifically the analyst's pricing finding) can see the seller's marketplace data.

### 4.3 [agents/scanner.py](agents/scanner.py)

Two functions:

- `scan(urls)` — live mode. Tries `scrape_product()` for each URL via `utils/scraper.py`. On any failure, picks a matching scenario from `sample_data.json` and returns its data instead.
- `load_scenario(scenario_id)` — demo mode. Skips the network entirely, reads the requested scenario directly from the JSON file.

Both return a dict with the same shape: `{seller, competitors, scenario_id}`. Scenario IDs are strings like `"yoga_mat"`, `"protein_powder"`, `"resistance_bands"` — six total.

### 4.4 [agents/tools.py](agents/tools.py)

Defines the three LLM-callable agent tools. Each tool has two pieces:

- A **JSON schema** (a structured description of the function's name, what it does, and what arguments it expects, formatted for the LLM API to read)
- A **Python handler** that does the actual work when the LLM emits a tool_call

The three tools:

- `fetch_competitor_listing(asin)` — HTTP GET to `https://www.amazon.com/dp/{asin}`, parses with BeautifulSoup. On Amazon block (HTTP 503 or CAPTCHA), looks up the matching competitor in the local sample data via the catalog ASIN map.
- `get_keyword_trend(keyword)` — uses the `pytrends` library (a Python wrapper around Google Trends' undocumented HTTP endpoint) to fetch the last 30 days of search interest. Returns interest score (0–100) and trend direction (rising/flat/falling). Has a 1-hour in-memory cache to avoid Google rate-limiting during repeat demos. Falls back to a heuristic estimate if Google is unreachable.
- `search_reddit_mentions(query)` — HTTP GET to Reddit's public search endpoint (no auth needed for read-only access). Returns up to 5 recent posts with title, subreddit, score (Reddit upvotes minus downvotes), and comment count.

### 4.5 [agents/investigator.py](agents/investigator.py)

The agentic loop. Roughly 200 lines. Takes the seller's product data and (optionally) the SKU's context dict, then runs Groq's chat completion API with `tools=TOOL_SCHEMAS` and `tool_choice="auto"`. On every iteration:

1. Send messages to Groq
2. If the response has `tool_calls`, execute each one via the registry, append the results as `role: tool` messages, loop again
3. If the response has no tool calls (or we hit 4 iterations / 5 total tool calls), stop and use the assistant's last text as the research notes

There's a fallback parser that handles a Llama 3.3 quirk: occasionally the model emits the legacy `<function=name(args)>` text format instead of using Groq's structured `tool_calls` field, which causes a 400 error. The investigator catches that error, parses the legacy format, and synthesizes a proper tool_call so the loop continues. Without this fallback, ~30% of runs would fail.

### 4.6 [agents/analyst.py](agents/analyst.py)

Four finding generators:

- `_keyword_gap` — pure Python. Tokenizes (splits text into individual words) the seller's title and bullets and the competitors' titles and bullets, drops stopwords (common words like "the", "and", "with" that don't carry meaning), counts how many competitors use each word, and returns the words that appear in 2+ competitors but not in the seller. No LLM call.
- `_sentiment` — calls Groq with `SENTIMENT_PROMPT` on the seller's 20 most recent reviews. Returns the top complaint and how many reviews mention it.
- `_hook` — calls Groq with `HOOK_PROMPT` to compare the seller's title to competitors' titles. Returns scores 1–10 for both and a one-sentence gap explanation.
- `_pricing_opportunity` — pure Python plus an HTTP call. Reads the SKU's `marketplaces` field (a dict of region → price_local + currency), calls `utils/fx.to_usd()` (which calls open.er-api.com to get current FX rates and converts every price to USD-equivalent), finds the biggest deviation from the median, and returns a finding if the gap is ≥10%.

Each finding is a dict with shape:

```python
{
    "type": "keyword_gap" | "review_complaint" | "weak_hook" | "pricing_opportunity",
    "description": "human-readable issue",
    "severity": int,         # 1-10
    "frequency": int,        # 1-10
    "revenue_impact": int,   # 1-10
    "data": {...},           # type-specific payload the executor needs
}
```

### 4.7 [agents/decider.py](agents/decider.py)

Takes the findings list, computes Impact Score (severity × frequency × revenue_impact, max 1000) for each, sorts descending, takes the top 3. If fewer than 3 findings exist, pads by duplicating the lowest-scored one with a small Impact Score decay so cards stay distinct. Adds a `category` field by mapping `type` → category:

- `keyword_gap → listing`
- `review_complaint → review`
- `weak_hook → social`
- `pricing_opportunity → pricing`

Always returns exactly 3 priorities. Each gets a `rank` field (1, 2, or 3).

### 4.8 [agents/executor.py](agents/executor.py)

For each priority, dispatch by category to one of four handlers (`_execute_listing`, `_execute_review`, `_execute_social`, `_execute_pricing`). Each handler:

1. Pulls type-specific data from `priority["data"]`
2. Formats the matching prompt template from [utils/prompts.py](utils/prompts.py)
3. Calls Groq via `call_with_tokens()` (which returns both the response text and the token count for cost tracking)
4. Returns the trimmed text and tokens

Wraps each call in try/except. On any failure, sets `output = "Output unavailable — please retry."` and `tokens = 0`. Builds the final 3-card payload.

### 4.9 [utils/prompts.py](utils/prompts.py)

All five LLM prompts as Python f-string templates. Centralised here so you can tune prompts without touching pipeline code. The five:

- `SENTIMENT_PROMPT` — used by analyst._sentiment
- `HOOK_PROMPT` — used by analyst._hook
- `LISTING_REWRITE_PROMPT` — used by executor._execute_listing
- `REVIEW_REPLY_PROMPT` — used by executor._execute_review
- `SOCIAL_PROMPT` — used by executor._execute_social
- `PRICING_REWRITE_PROMPT` — used by executor._execute_pricing

### 4.10 [utils/claude_client.py](utils/claude_client.py)

Thin wrapper around Groq's SDK (Software Development Kit, the official Python library Groq publishes for talking to its API). Function names are kept generic (`call_claude`, `call_claude_json`, `call_with_tokens`) so swapping LLM providers later requires editing one file.

- `call_claude(prompt)` — sends a prompt, returns text
- `call_claude_json(prompt)` — sends a prompt expecting JSON, parses safely (strips any preamble text before the first `{` and trailing junk after `}`)
- `call_with_tokens(prompt)` — same as `call_claude` but returns `(text, total_tokens)` for cost tracking

### 4.11 [utils/scraper.py](utils/scraper.py)

`scrape_product(url)` — uses `requests` (the standard Python HTTP library) and `BeautifulSoup` (an HTML-parsing library) to pull title, bullets, price, rating, review count, and 20 reviews from an Amazon listing URL. 10-second timeout. Raises on any failure so the caller can fall back.

### 4.12 [utils/db.py](utils/db.py)

SQLite (a lightweight, file-based relational database that's part of Python's standard library — no install needed) wrapper. Two tables: `approved_actions` and `denied_actions`, each with rank, category, issue, output, Impact Score, scenario_id, timestamp.

Functions: `init_db()` (idempotent table creation), `save_approved()`, `save_denied()`, `get_history(limit=50)`, `get_stats()` (totals, by_category, this_week), `get_weekly_trend()` (7 days of approval/denial counts).

### 4.13 [utils/fx.py](utils/fx.py)

Foreign exchange rates from `open.er-api.com` (a free API that returns USD-base exchange rates with no key required). 1-hour in-memory cache so the pipeline doesn't hammer the endpoint. Falls back to a hardcoded rate table if the API is unreachable. Used by `analyst._pricing_opportunity` to convert each marketplace's local price to USD-equivalent.

### 4.14 [utils/notifier.py](utils/notifier.py)

Console-only logger. Functions `send_morning_briefing(actions)` and `send_alert(subject, body)` write formatted output to stdout. Earlier versions sent email (SendGrid) and Slack messages, but the product direction shifted to "everything stays inside Pixii — no external apps for sellers." Kept the function names so the monitors don't need to change.

### 4.15 [utils/pixii_simulator.py](utils/pixii_simulator.py)

Loads `data/pixii_catalog.json` and exposes `get_catalog()`, `get_skus()`, `pick_priority_sku()` (returns the SKU with the highest priority_score), and `fmt_seller_header()` (formats `"PrimeBrands Co. (Pixii ID: PB-00417)"` for the UI). In production, every function in this file would be replaced by a Pixii API call.

### 4.16 [scheduler.py](scheduler.py)

Uses APScheduler (a Python library for cron-style scheduled jobs in-process) to run `daily_oracle_run()` at 8:00 AM every day. Started by the UI on first load via `start_scheduler()`. The job runs the pipeline on the default scenario and logs the briefing to the console.

### 4.17 [review_watcher.py](review_watcher.py)

Watches the seller's reviews for new complaint patterns. Loads the previous review snapshot from `data/review_snapshots.json`, compares with current reviews, tokenizes the *new* reviews, and counts mentions of 15 complaint stems (`clump`, `snap`, `loud`, `smell`, `break`, etc.). If any stem appears 3+ times across new reviews, fires `send_alert()`. The `demo_trigger()` function injects 5 fake "snaps easily" reviews to demonstrate the alert.

### 4.18 [competitor_monitor.py](competitor_monitor.py)

Watches competitor listings for three change types: price drops over 5%, addition of 3+ new keywords, or rating drops below 4.0. Stores snapshots in `data/competitor_snapshots.json`. The `demo_trigger()` function simulates a 15% price drop on a competitor.

---

## 5. The agentic loop in detail

The investigator runs a chat-completion loop with Groq. Here's what happens, message by message, on a typical run:

**Round 1 — initial request:**

```
system: You are an Amazon listing investigator. You have three tools: ...
user:   Seller listing: "MaxFuel Whey Protein..." 
        Detected missing keywords: mix, clumps, formula, instant, easy
        Competitors: ASIN B0PWHEY9911, ASIN B0FFLEX5522
        Priority reason: Review velocity skewing negative...
```

The LLM thinks about it (internally — we don't see chain-of-thought) and decides to call tools. Its response includes:

```
assistant: tool_calls = [
  {id: 'call_001', name: 'fetch_competitor_listing', arguments: '{"asin":"B0PWHEY9911"}'},
  {id: 'call_002', name: 'get_keyword_trend', arguments: '{"keyword":"easy mix"}'},
  {id: 'call_003', name: 'get_keyword_trend', arguments: '{"keyword":"dissolve"}'},
  {id: 'call_004', name: 'search_reddit_mentions', arguments: '{"query":"whey protein mixing"}'},
]
```

**The Python loop executes each tool** and adds the results as messages:

```
tool (call_001): {source: 'sample_fallback', title: 'PrimeWhey Easy Mix Formula...'}
tool (call_002): {keyword: 'easy mix', interest: 64, trend: 'falling'}
tool (call_003): {keyword: 'dissolve', interest: 77, trend: 'falling'}
tool (call_004): {posts: [{title: '[Acne] Cutting out dairy...', subreddit: 'AcneScars', ...}]}
```

**Round 2 — feed results back, ask for summary:**

The LLM sees the tool results and decides it has enough. Its second response has no tool calls, just text:

```
assistant: We investigated the seller's listing and competitors, and found that the
           competitor with ASIN B0PWHEY9911 has a product with an "easy mix formula"...
```

That text becomes the **research notes** in the UI panel.

The whole loop is bounded: max 4 iterations and max 5 tool calls total. After that, the investigator forces a summary turn and stops.

---

## 6. The Impact Score formula and the "Why this priority?" expander

Impact Score = **Severity × Frequency × Revenue Impact**

Each component is an integer 1–10, so Impact Score ranges 0–1000.

- **Severity** — how bad the issue is when it manifests. A keyword gap that hits 6 of your 5 bullets is severe; a hook gap that's only 1 point worse than competitors is not.
- **Frequency** — how often the issue manifests. A keyword that 3 competitors use is high-frequency; a single review complaint is low.
- **Revenue Impact** — how directly this issue affects sales. A weak hook costs clicks across every visitor (high impact). A pricing gap directly affects every sale (highest impact). A keyword gap compounds over time (medium impact).

The ratings come from each finding generator. Examples:

| Finding type | Severity rule | Frequency rule | Revenue impact (constant) |
| --- | --- | --- | --- |
| keyword_gap | min(10, len(top_gaps)) | min(10, max_competitor_count × 3) | 8 |
| review_complaint | min(10, complaint_freq) | min(10, complaint_freq) | 7 |
| weak_hook | min(10, score_gap × 2) | 5 (constant) | 9 |
| pricing_opportunity | min(10, deviation_pct × 50) | 6 (constant) | 9 |

The Impact Score for a 28% pricing deviation in DE marketplace is therefore 10 × 6 × 9 = **540**, beating most other findings. That's why pricing cards rise to the top when they fire.

---

## 7. The four data files

### 7.1 [data/sample_data.json](data/sample_data.json)

Six product scenarios, each with a seller listing and two competitor listings. Every listing has title, 5 bullets, description, price, rating, review_count, and 20 realistic-sounding reviews. The reviews are pre-baked so each scenario reliably surfaces the issue it's named after — e.g. the protein powder seller has 12 reviews mentioning clumping, the resistance bands seller has 7 mentioning snapping.

### 7.2 [data/pixii_catalog.json](data/pixii_catalog.json)

Simulates the SKU record Pixii would have for `PrimeBrands Co.`. Six SKUs (one per scenario). Each SKU has `sku_id`, `asin`, `title`, `category`, `scenario_id` (links to sample_data), `last_analysis_date`, `conversion_rate_30d` and trend, `ad_spend_30d_usd`, `rank_change_7d`, `priority_score` (0–100), `priority_reason` (plain English), `competitive_set_asins` (the ASINs of competitors), and `marketplaces` (a dict of region → local price + currency for cross-marketplace pricing analysis).

### 7.3 `data/review_snapshots.json` (auto-created)

A dict of scenario_id → previous review list. Used by `review_watcher.py` to detect new reviews. Created the first time the watcher runs.

### 7.4 `data/competitor_snapshots.json` (auto-created)

A dict of scenario_id → competitor key → previous price/rating/tokens. Used by `competitor_monitor.py` to detect changes.

---

## 8. External APIs and tools used

The project uses **four real external APIs** beyond the LLM:

| API | What it does | Where it's called | Auth |
| --- | --- | --- | --- |
| **Amazon (HTTP scrape)** | Fetch a competitor's listing | [utils/scraper.py](utils/scraper.py), [agents/tools.py](agents/tools.py) (as `fetch_competitor_listing`) | None (User-Agent only) |
| **Google Trends (pytrends)** | Validate keyword search demand | [agents/tools.py](agents/tools.py) (as `get_keyword_trend`) | None |
| **Reddit JSON API** | Search outside-Amazon mentions | [agents/tools.py](agents/tools.py) (as `search_reddit_mentions`) | None for read |
| **Open Exchange Rates** | Convert local prices to USD | [utils/fx.py](utils/fx.py) (used by analyst._pricing_opportunity) | None |

Three of those are wrapped as **agent tools** (functions registered with the LLM via Groq's function-calling API, which the LLM decides to invoke). The fourth (Open Exchange Rates) is consumed deterministically by the analyst — the LLM doesn't decide whether to call it; the analyst always calls it when the SKU has multi-marketplace data.

The local stack also includes **SQLite** (file-based database for history), **APScheduler** (in-process cron), **Streamlit + Plotly** (UI), **BeautifulSoup** (HTML parsing). All free, no external apps required from the seller.

---

## 9. Why this architecture serves both seller and Pixii

**For the seller.** The seller's only daily action is OK or Deny on three cards. They don't paste URLs, read 100 reviews, search for missing keywords, compare competitors, calculate cross-marketplace pricing, or write any copy. Everything that's a decision is decided. Everything that's content is written. Their morning shrinks from 90 minutes of dashboard work to 2 minutes.

**For Pixii.** Four direct revenue levers:

1. **Higher seller ARPU** (Average Revenue Per User, the per-customer recurring fee). Cross-marketplace pricing is a paid-tier feature in Helium 10 and Jungle Scout. Pixii bundles it natively.
2. **Lower churn.** Daily approve/deny creates a habit loop. Habit users churn 60% less than occasional users.
3. **Marketplace expansion drives upsells.** The pricing card actively suggests new marketplaces. Sellers expanding internationally buy more Pixii (translation, multi-region PPC, regional inventory).
4. **Defensibility.** History DB + per-SKU priority scoring + per-seller approved-voice memory all compound. The longer a seller stays, the better their personal Pixii Pulse gets, the harder it is to leave.

---

## 10. How to run and test

```powershell
# install deps
pip install -r requirements.txt

# add your Groq API key to .env
# GROQ_API_KEY="your groq api key here "

# headless smoke test (prints the 3-card payload + investigation trace)
python main.py

# review-monitor demo trigger
python review_watcher.py

# competitor-monitor demo trigger  
python competitor_monitor.py

# the UI
streamlit run app.py
# → http://localhost:8501
# → password: pixii2026
```

Inside the UI: login → Daily Actions → click Generate → expand the investigator panel → review the 3 cards → click OK or Deny → optionally browse to History & Trends, Review Monitor, Competitor Monitor, or Settings.

---

End of walkthrough.
