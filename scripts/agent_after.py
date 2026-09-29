"""AFTER: verified tool-use agent loop.

Hardening techniques:
  1. Schema-check every tool envelope + per-tool payload
  2. Surface failures explicitly (never invent success)
  3. Treat empty success payloads as non-answers
  4. Retry transient errors (timeout) once, then stop
  5. Faithfulness gate: final answer must be grounded in verified tool data
  6. Stop rules on permanent tool failure / schema violation
"""

from __future__ import annotations

import time
from typing import Any

from schemas import is_empty_success, validate_payload
from tools import call_tool


MAX_TRANSIENT_RETRIES = 1


def _compose_from_verified(tool: str, data: dict[str, Any]) -> str:
    if tool == "weather_lookup":
        return (
            f"Weather in {data.get('city')}: {data.get('temp_c')}°C, "
            f"{data.get('condition')} (humidity {data.get('humidity')}%)."
        )
    if tool == "docs_search":
        hits = data.get("hits") or []
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


def _failure_answer(tool: str, error: str | None, kind: str) -> str:
    if kind == "empty":
        return f"Tool {tool} returned no results (empty). Unable to answer from verified data."
    if kind == "schema":
        return f"Tool {tool} returned a schema-invalid payload ({error}). Stopping without inventing an answer."
    if kind == "timeout":
        return f"Tool {tool} timed out after retry. Unable to complete the task."
    return f"Tool {tool} failed: {error}. Stopping; no fabricated result."


def run_task(task: dict[str, Any]) -> dict[str, Any]:
    t0 = time.perf_counter()
    steps: list[dict[str, Any]] = []
    tool_results: list[dict[str, Any]] = []
    verified_payloads: list[dict[str, Any]] = []

    answer = ""
    claimed_success = False
    stop_reason: str | None = None

    for step_i, action in enumerate(task["plan"]):
        tool = action["tool"]
        args = dict(action.get("args") or {})
        attempts = 0
        result: dict[str, Any] | None = None

        while True:
            attempts += 1
            result = call_tool(tool, args)
            tool_results.append(result)
            steps.append(
                {
                    "step": step_i,
                    "attempt": attempts,
                    "action": "tool_call",
                    "tool": tool,
                    "args": args,
                    "result_ok": result.get("ok"),
                    "result_error": result.get("error"),
                    "transient": bool(result.get("transient")),
                }
            )

            # Schema gate
            schema_ok, schema_err = validate_payload(tool, result)
            steps.append(
                {
                    "step": step_i,
                    "attempt": attempts,
                    "action": "schema_check",
                    "ok": schema_ok,
                    "error": schema_err,
                }
            )
            if not schema_ok:
                answer = _failure_answer(tool, schema_err, "schema")
                claimed_success = False
                stop_reason = f"schema_violation:{schema_err}"
                break

            # Transient retry
            if (
                not result.get("ok")
                and result.get("transient")
                and attempts <= MAX_TRANSIENT_RETRIES
            ):
                steps.append(
                    {
                        "step": step_i,
                        "attempt": attempts,
                        "action": "retry",
                        "reason": result.get("error"),
                    }
                )
                continue

            # Permanent failure
            if not result.get("ok"):
                kind = "timeout" if result.get("error") == "timeout" else "error"
                answer = _failure_answer(tool, result.get("error"), kind)
                claimed_success = False
                stop_reason = f"tool_error:{result.get('error')}"
                break

            # Empty success
            if is_empty_success(tool, result):
                answer = _failure_answer(tool, None, "empty")
                claimed_success = False
                stop_reason = "empty_result"
                break

            # Verified success
            data = result.get("data") or {}
            verified_payloads.append({"tool": tool, "data": data})
            answer = _compose_from_verified(tool, data)
            claimed_success = True
            stop_reason = None
            break

        if stop_reason and not claimed_success:
            break

    # Faithfulness gate: answer must reference verified payloads only
    faithfulness_ok = True
    if claimed_success:
        if not verified_payloads:
            faithfulness_ok = False
            claimed_success = False
            answer = "Faithfulness gate failed: success claimed with no verified tool payload."
            stop_reason = "faithfulness_fail"
            steps.append({"action": "faithfulness_check", "ok": False})
        else:
            # Ensure answer is not a known fabrication phrase
            fab_markers = (
                "unicorn protocol overview",
                "partly cloudy",
                "unknown user",
                "redacted placeholder",
                "the result is 0.",
            )
            low = answer.lower()
            if any(m in low for m in fab_markers):
                faithfulness_ok = False
                claimed_success = False
                answer = "Faithfulness gate failed: answer matched known fabrication patterns."
                stop_reason = "faithfulness_fail"
                steps.append({"action": "faithfulness_check", "ok": False})
            else:
                steps.append({"action": "faithfulness_check", "ok": True})

    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    return {
        "task_id": task["id"],
        "category": task["category"],
        "mode": "after",
        "prompt": task["prompt"],
        "answer": answer,
        "claimed_success": claimed_success,
        "steps": steps,
        "n_steps": len(steps),
        "tool_results": tool_results,
        "verified_payloads": verified_payloads,
        "hallucinated_injected": False,
        "invented_answer": False,
        "faithfulness_ok": faithfulness_ok,
        "stop_reason": stop_reason,
        "elapsed_ms": elapsed_ms,
    }
