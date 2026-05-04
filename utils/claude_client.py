"""Thin wrapper around the Groq SDK.

Centralises model choice, JSON-extraction, token tracking, and timeout
handling so every agent can do `from utils.claude_client import call_claude,
call_claude_json` without repeating boilerplate. Function names retained
for backwards compatibility with analyst.py and executor.py.
"""
from __future__ import annotations

import json
import os
from typing import Any

from dotenv import load_dotenv
from groq import Groq

load_dotenv()

_MODEL = os.getenv("ORACLE_MODEL", "llama-3.3-70b-versatile")
_MAX_TOKENS = 1024
_TIMEOUT = 30.0

_client: Groq | None = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY not set. Copy .env.example to .env and add your key "
                "from https://console.groq.com/keys"
            )
        _client = Groq(api_key=api_key, timeout=_TIMEOUT)
    return _client


def _raw_call(prompt: str, max_tokens: int) -> tuple[str, int]:
    """Send the prompt, return (text, total_tokens). Raises on SDK error."""
    client = _get_client()
    resp = client.chat.completions.create(
        model=_MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    text = (resp.choices[0].message.content or "").strip()
    tokens = 0
    if getattr(resp, "usage", None) is not None:
        tokens = int(getattr(resp.usage, "total_tokens", 0) or 0)
    return text, tokens


def call_claude(prompt: str, max_tokens: int = _MAX_TOKENS) -> str:
    """Send a prompt, return the raw text response."""
    text, _tokens = _raw_call(prompt, max_tokens)
    return text


def call_with_tokens(prompt: str, max_tokens: int = _MAX_TOKENS) -> tuple[str, int]:
    """Send a prompt, return (text, total_tokens). Used by executor for cost tracking."""
    return _raw_call(prompt, max_tokens)


def _extract_json(text: str) -> str:
    """Strip any preamble before the first { and any trailing junk after }."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError(f"no JSON object in response: {text[:200]}")
    return text[start : end + 1]


def call_claude_json(prompt: str, max_tokens: int = _MAX_TOKENS) -> dict[str, Any]:
    """Send a prompt expected to return JSON. Strips preamble, parses safely."""
    raw = call_claude(prompt, max_tokens=max_tokens)
    try:
        return json.loads(_extract_json(raw))
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"LLM returned invalid JSON: {exc}\nRaw: {raw[:500]}") from exc


def call_json_with_tokens(
    prompt: str, max_tokens: int = _MAX_TOKENS
) -> tuple[dict[str, Any], int]:
    """JSON variant of call_with_tokens."""
    raw, tokens = call_with_tokens(prompt, max_tokens=max_tokens)
    try:
        return json.loads(_extract_json(raw)), tokens
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"LLM returned invalid JSON: {exc}\nRaw: {raw[:500]}") from exc
