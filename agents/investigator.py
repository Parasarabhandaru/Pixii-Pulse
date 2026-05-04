"""INVESTIGATE agent — Step 2.5 in the ORACLE pipeline.

Runs an agentic LLM loop. Given the seller's listing + detected missing
keywords + competitor list, the LLM **decides** which of two tools to
call, in what order, to gather context before the analyst runs.

Tools available (see agents/tools.py):
  • fetch_competitor_listing(asin)  — real Amazon HTTP fetch
  • get_keyword_trend(keyword)      — real Google Trends HTTP call

Returns:
  {
    "research_notes": str,                # 2-3 sentence summary the LLM produced
    "tool_calls": [                       # full trace for the UI
      {"iteration": int, "tool": str, "args": {...}, "result_preview": str},
      ...
    ],
    "raw_results": {
      "keyword_trends":      {keyword: result_dict},
      "competitor_drilldowns": {asin: result_dict},
    }
  }
"""
from __future__ import annotations

import json
import os
import re
import uuid
from collections import Counter

from dotenv import load_dotenv
from groq import BadRequestError, Groq

from .tools import TOOL_REGISTRY, TOOL_SCHEMAS

_LEGACY_TOOL_RE = re.compile(
    r"<function\s*=\s*([\w_]+)\s*\((\{.*?\})\s*\)\s*>?",
    re.DOTALL,
)

load_dotenv()

_MODEL = os.getenv("ORACLE_MODEL", "llama-3.3-70b-versatile")
_MAX_ITERATIONS = 4
_MAX_TOOLS_TOTAL = 5

_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "for", "with", "of", "to", "in", "on",
    "at", "by", "from", "is", "it", "its", "this", "that", "are", "was", "be",
    "as", "you", "your", "we", "our", "they", "their", "have", "has", "use",
    "made", "great", "good", "best", "premium", "quality", "design", "designed",
}
_TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z\-]+")


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or "") if len(t) > 2]


def _detect_missing_keywords(scan_data: dict) -> list[str]:
    seller = scan_data.get("seller", {})
    seller_blob = (seller.get("title") or "") + " " + " ".join(seller.get("bullets") or [])
    seller_tokens = {t for t in _tokenize(seller_blob) if t not in _STOPWORDS}

    counter: Counter[str] = Counter()
    for comp in scan_data.get("competitors", []):
        comp_blob = (comp.get("title") or "") + " " + " ".join(comp.get("bullets") or [])
        for tok in _tokenize(comp_blob):
            if tok not in _STOPWORDS:
                counter[tok] += 1

    return [
        tok for tok, count in counter.most_common(10)
        if count >= 2 and tok not in seller_tokens
    ][:6]


def _build_initial_messages(scan_data: dict, sku_context: dict | None) -> list[dict]:
    seller = scan_data.get("seller", {})
    missing_keywords = _detect_missing_keywords(scan_data)

    asin_map = (sku_context or {}).get("competitive_set_asins") or []
    competitor_lines = []
    for i, comp in enumerate(scan_data.get("competitors", [])):
        asin = asin_map[i] if i < len(asin_map) else f"unknown_asin_{i}"
        competitor_lines.append(f"  - ASIN {asin}: {(comp.get('title') or '')[:90]}")

    priority_reason = (sku_context or {}).get("priority_reason") or ""

    system = (
        "You are an Amazon listing investigator. Before our analyst recommends "
        "actions, you gather context. You have three tools:\n"
        "  1. fetch_competitor_listing(asin) — pull a specific competitor's listing\n"
        "  2. get_keyword_trend(keyword)     — check real Google Trends demand for a keyword\n"
        "  3. search_reddit_mentions(query)  — see how the brand/category is talked about on Reddit\n\n"
        "Rules:\n"
        "  • Be efficient. Call AT MOST 5 tools total across all your turns.\n"
        "  • Pick the 1-2 missing keywords most worth validating with Google Trends.\n"
        "  • If a competitor is mentioned in the priority reason, fetch their listing.\n"
        "  • Use Reddit search ONCE if you suspect outside-Amazon sentiment matters here.\n"
        "  • When done, stop calling tools and write a 2-3 sentence summary of what you learned."
    )

    user_lines = [
        f"Seller listing title: {seller.get('title', '')}",
        f"Seller first bullet:  {(seller.get('bullets') or [''])[0]}",
        "",
        "Detected missing keywords (used by 2+ competitors but not by seller):",
        f"  {', '.join(missing_keywords) or '(none detected)'}",
        "",
        "Competitors:",
        *competitor_lines,
    ]
    if priority_reason:
        user_lines += ["", f"Priority reason from Pixii: {priority_reason}"]
    user_lines += [
        "",
        "Investigate using your tools, then summarize. Begin.",
    ]

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": "\n".join(user_lines)},
    ]


def _parse_legacy_tool_calls(failed_generation: str) -> list[dict]:
    """Parse Llama's older `<function=NAME({args})>` text into Groq tool_call dicts."""
    parsed: list[dict] = []
    for match in _LEGACY_TOOL_RE.finditer(failed_generation or ""):
        name = match.group(1).strip()
        args_str = match.group(2).strip()
        try:
            json.loads(args_str)
        except json.JSONDecodeError:
            args_str = "{}"
        parsed.append({
            "id": f"legacy_{uuid.uuid4().hex[:8]}",
            "type": "function",
            "function": {"name": name, "arguments": args_str},
        })
    return parsed


def _attempt_chat(client: Groq, messages: list[dict]) -> tuple[object | None, list[dict]]:
    """Call Groq; if the model emitted legacy tool syntax, recover from the error.

    Returns (response_object_or_None, recovered_tool_calls).
    Exactly one of those will be non-empty when this succeeds.
    """
    try:
        response = client.chat.completions.create(
            model=_MODEL,
            messages=messages,
            tools=TOOL_SCHEMAS,
            tool_choice="auto",
            max_tokens=800,
        )
        return response, []
    except BadRequestError as exc:
        body = {}
        try:
            body = exc.response.json()
        except Exception:
            pass
        err = body.get("error") or {}
        if err.get("code") == "tool_use_failed":
            recovered = _parse_legacy_tool_calls(err.get("failed_generation", ""))
            if recovered:
                print(
                    f"[investigator] recovered {len(recovered)} legacy-format tool call(s) "
                    f"from llama"
                )
                return None, recovered
        raise


def _serialize_tool_calls(msg) -> list[dict] | None:
    """Convert Groq SDK tool_call objects into the dict shape the API expects on round-trip."""
    if not getattr(msg, "tool_calls", None):
        return None
    return [
        {
            "id": tc.id,
            "type": "function",
            "function": {
                "name": tc.function.name,
                "arguments": tc.function.arguments,
            },
        }
        for tc in msg.tool_calls
    ]


def investigate(scan_data: dict, sku_context: dict | None = None) -> dict:
    """Run the agentic loop and return the research bundle."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return {
            "research_notes": "Investigator skipped — GROQ_API_KEY not set.",
            "tool_calls": [],
            "raw_results": {"keyword_trends": {}, "competitor_drilldowns": {}},
        }

    client = Groq(api_key=api_key, timeout=30.0)
    messages = _build_initial_messages(scan_data, sku_context)

    tool_call_log: list[dict] = []
    raw_results: dict = {"keyword_trends": {}, "competitor_drilldowns": {}}
    tools_used = 0

    for iteration in range(1, _MAX_ITERATIONS + 1):
        try:
            response, recovered = _attempt_chat(client, messages)
        except Exception as exc:
            print(f"[investigator] LLM call failed at iteration {iteration}: {exc}")
            return {
                "research_notes": f"Investigation aborted: {exc}",
                "tool_calls": tool_call_log,
                "raw_results": raw_results,
            }

        if recovered:
            # Model emitted legacy XML format. Synthesize a tool_calls turn so
            # the loop continues normally.
            messages.append({"role": "assistant", "content": None, "tool_calls": recovered})
            class _FakeTC:
                def __init__(self, d):
                    self.id = d["id"]
                    class _F:
                        def __init__(self, fd):
                            self.name = fd["name"]
                            self.arguments = fd["arguments"]
                    self.function = _F(d["function"])
            tool_calls_iter = [_FakeTC(d) for d in recovered]
        else:
            msg = response.choices[0].message
            assistant_entry = {"role": "assistant", "content": msg.content or ""}
            serialized = _serialize_tool_calls(msg)
            if serialized:
                assistant_entry["tool_calls"] = serialized
            messages.append(assistant_entry)

            if not msg.tool_calls:
                return {
                    "research_notes": (msg.content or "").strip(),
                    "tool_calls": tool_call_log,
                    "raw_results": raw_results,
                }
            tool_calls_iter = msg.tool_calls

        for tc in tool_calls_iter:
            tools_used += 1
            tool_name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}

            handler = TOOL_REGISTRY.get(tool_name)
            if handler is None:
                result = {"error": f"unknown tool: {tool_name}"}
            else:
                try:
                    result = handler(**args)
                except Exception as exc:
                    result = {"error": str(exc)}

            tool_call_log.append({
                "iteration": iteration,
                "tool": tool_name,
                "args": args,
                "result_preview": str(result)[:160],
            })

            if tool_name == "get_keyword_trend":
                raw_results["keyword_trends"][args.get("keyword", "?")] = result
            elif tool_name == "fetch_competitor_listing":
                raw_results["competitor_drilldowns"][args.get("asin", "?")] = result

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "name": tool_name,
                "content": json.dumps(result),
            })

            if tools_used >= _MAX_TOOLS_TOTAL:
                break

        if tools_used >= _MAX_TOOLS_TOTAL:
            break

    # Ran out of iterations or tool budget — force a final summary turn.
    messages.append({
        "role": "user",
        "content": "Stop calling tools. In 2-3 sentences, summarize what you learned.",
    })
    try:
        final = client.chat.completions.create(
            model=_MODEL,
            messages=messages,
            max_tokens=300,
        )
        notes = (final.choices[0].message.content or "").strip()
    except Exception as exc:
        notes = f"Investigation summary unavailable: {exc}"

    return {
        "research_notes": notes,
        "tool_calls": tool_call_log,
        "raw_results": raw_results,
    }
