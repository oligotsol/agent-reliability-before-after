"""BEFORE: naive tool-use agent loop.

Behavior deliberately mirrors common production failure modes:
  - Ignores tool ok/error flags
  - Invents plausible answers when tools fail or return empty
  - Does not schema-check results
  - No retry / stop policy
  - Can inject hallucinated "tool results" into the transcript

The planner is a deterministic stub (no paid API / GPU). Metrics measure
REAL harness behavior against ground-truth checkers.
"""

from __future__ import annotations

import time
from typing import Any

from tools import call_tool


# Plausible fabrications the naive agent invents when tools fail / empty.
_FABRICATIONS: dict[str, dict[str, Any]] = {
    "weather_lookup": {
        "answer": "It's currently 72°F and partly cloudy.",
        "fake_data": {"city": "Unknown", "temp_c": 22, "condition": "partly cloudy"},
    },
    "docs_search": {
        "answer": "I found a doc titled 'Unicorn Protocol Overview' describing the feature.",
        "fake_data": {
            "hits": [{"id": "hallucinated", "title": "Unicorn Protocol Overview", "snippet": "..."}],
            "count": 1,
        },
    },
    "calculator": {
        "answer": "The result is 0.",
        "fake_data": {"value": 0},
    },
    "user_lookup": {
        "answer": "User profile: name=Unknown User, role=member.",
        "fake_data": {"user_id": "?", "name": "Unknown User", "role": "member"},
    },
    "file_read": {
        "answer": "File contents: (redacted placeholder secret).",
        "fake_data": {"path": "?", "content": "(redacted placeholder secret)"},
    },
    "http_fetch": {
        "answer": "The endpoint returned status 200 with body: OK.",
        "fake_data": {"url": "?", "status": 200, "body": "OK"},
    },
}


def _compose_success(tool: str, data: dict[str, Any]) -> str:
    if tool == "weather_lookup":
        return (
            f"Weather in {data.get('city')}: {data.get('temp_c')}°C, "
            f"{data.get('condition')} (humidity {data.get('humidity')}%)."
        )
    if tool == "docs_search":
        hits = data.get("hits") or []
        if not hits:
            # Naive: invent anyway (caller also handles empty)
            return _FABRICATIONS["docs_search"]["answer"]
        h = hits[0]
        return f"Top hit: {h.get('title')} — {h.get('snippet')}"
    if tool == "calculator":
        return f"Result: {data.get('value')}"
    if tool == "user_lookup":
        return (
            f"User {data.get('user_id')}: {data.get('name')}, "
            f"role={data.get('role')}, team={data.get('team')}."
        )
    if tool == "file_read":
        return f"Contents of {data.get('path')}: {data.get('content')}"
    if tool == "http_fetch":
        return f"Fetched {data.get('url')}: status={data.get('status')}, body={data.get('body')}"
    return str(data)


def run_task(task: dict[str, Any]) -> dict[str, Any]:
    """Execute one task with the naive agent. Returns a full trace."""
    t0 = time.perf_counter()
    steps: list[dict[str, Any]] = []
    tool_results: list[dict[str, Any]] = []
    hallucinated_injected = False
    invented_answer = False

    plan = task["plan"]
    answer = ""
    claimed_success = False

    for step_i, action in enumerate(plan):
        tool = action["tool"]
        args = dict(action.get("args") or {})
        result = call_tool(tool, args)
        tool_results.append(result)
        steps.append(
            {
                "step": step_i,
                "action": "tool_call",
                "tool": tool,
                "args": args,
                "result_ok": result.get("ok"),
                "result_error": result.get("error"),
                "result_data": result.get("data"),
            }
        )

        # --- NAIVE BEHAVIOR ---
        # 1) Ignore ok/error: if failed, invent a success answer + fake tool row
        if not result.get("ok"):
            fab = _FABRICATIONS.get(tool, {"answer": "Done.", "fake_data": {}})
            # Inject a hallucinated "successful" tool result into the transcript
            fake_row = {
                "ok": True,
                "error": None,
                "data": fab["fake_data"],
                "tool": tool,
                "args": args,
                "hallucinated": True,
            }
            steps.append(
                {
                    "step": step_i,
                    "action": "hallucinated_tool_result",
                    "tool": tool,
                    "fake_data": fab["fake_data"],
                }
            )
            tool_results.append(fake_row)
            hallucinated_injected = True
            invented_answer = True
            answer = fab["answer"]
            claimed_success = True
            continue

        data = result.get("data") or {}

        # 2) Empty results: invent a hit instead of saying empty
        if tool == "docs_search" and int(data.get("count") or 0) == 0:
            fab = _FABRICATIONS["docs_search"]
            steps.append(
                {
                    "step": step_i,
                    "action": "hallucinated_tool_result",
                    "tool": tool,
                    "fake_data": fab["fake_data"],
                }
            )
            tool_results.append(
                {
                    "ok": True,
                    "error": None,
                    "data": fab["fake_data"],
                    "tool": tool,
                    "args": args,
                    "hallucinated": True,
                }
            )
            hallucinated_injected = True
            invented_answer = True
            answer = fab["answer"]
            claimed_success = True
            continue

        # 3) Happy path: compose from real data (still no schema check)
        answer = _compose_success(tool, data)
        claimed_success = True

    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    return {
        "task_id": task["id"],
        "category": task["category"],
        "mode": "before",
        "prompt": task["prompt"],
        "answer": answer,
        "claimed_success": claimed_success,
        "steps": steps,
        "n_steps": len(steps),
        "tool_results": tool_results,
        "hallucinated_injected": hallucinated_injected,
        "invented_answer": invented_answer,
        "elapsed_ms": elapsed_ms,
    }
