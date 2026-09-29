"""Metric extraction over agent traces.

Definitions (applied uniformly to BEFORE and AFTER):
  silent_failure
      Agent claimed_success=True while any real tool call in the trace failed
      OR returned an empty success payload (docs count=0, etc.), OR the agent
      injected a hallucinated tool result. This is the core industry pain.
  hallucinated_tool_result
      Trace contains an injected fake tool row (BEFORE) OR final answer makes
      factual claims absent from any non-hallucinated tool payload.
  task_success
      Ground-truth checker for the task returns True.
"""

from __future__ import annotations

from typing import Any

from schemas import is_empty_success
from tasks import evaluate_task


def _real_tool_rows(trace: dict[str, Any]) -> list[dict[str, Any]]:
    """Tool results that came from the actual tool registry (not injected fakes)."""
    rows = []
    for r in trace.get("tool_results") or []:
        if r.get("hallucinated"):
            continue
        rows.append(r)
    return rows


def score_trace(task: dict[str, Any], trace: dict[str, Any]) -> dict[str, Any]:
    real = _real_tool_rows(trace)
    any_tool_failed = any(not r.get("ok") for r in real)
    any_empty = any(is_empty_success(r.get("tool", ""), r) for r in real if r.get("ok"))
    hallucinated = bool(trace.get("hallucinated_injected")) or any(
        s.get("action") == "hallucinated_tool_result" for s in (trace.get("steps") or [])
    )

    # Silent failure: claimed success despite failed/empty tool OR hallucinated result
    silent_failure = bool(trace.get("claimed_success")) and (
        any_tool_failed or any_empty or hallucinated or bool(trace.get("invented_answer"))
    )

    # Hallucinated-tool-result rate component
    hallucinated_tool_result = hallucinated or bool(trace.get("invented_answer"))

    # For AFTER success path: also flag if answer isn't grounded (faithfulness)
    if trace.get("mode") == "after" and trace.get("claimed_success"):
        if trace.get("faithfulness_ok") is False:
            hallucinated_tool_result = True
            silent_failure = True

    task_success = evaluate_task(task, trace)

    return {
        "task_id": task["id"],
        "category": task["category"],
        "claimed_success": bool(trace.get("claimed_success")),
        "silent_failure": silent_failure,
        "hallucinated_tool_result": hallucinated_tool_result,
        "task_success": task_success,
        "n_steps": int(trace.get("n_steps") or 0),
        "elapsed_ms": float(trace.get("elapsed_ms") or 0.0),
        "any_tool_failed": any_tool_failed,
        "any_empty": any_empty,
        "answer": trace.get("answer"),
        "stop_reason": trace.get("stop_reason"),
    }


def aggregate(scores: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(scores) or 1
    silent = sum(1 for s in scores if s["silent_failure"])
    hallu = sum(1 for s in scores if s["hallucinated_tool_result"])
    success = sum(1 for s in scores if s["task_success"])
    hard = [s for s in scores if s["category"] == "failure"]
    easy = [s for s in scores if s["category"] == "success"]
    hard_success = sum(1 for s in hard if s["task_success"])
    easy_success = sum(1 for s in easy if s["task_success"])
    mean_steps = sum(s["n_steps"] for s in scores) / n
    mean_latency = sum(s["elapsed_ms"] for s in scores) / n

    return {
        "n_tasks": len(scores),
        "silent_failure_count": silent,
        "silent_failure_rate": silent / n,
        "hallucinated_tool_result_count": hallu,
        "hallucinated_tool_result_rate": hallu / n,
        "task_success_count": success,
        "task_success_rate": success / n,
        "hard_task_count": len(hard),
        "hard_task_success_count": hard_success,
        "hard_task_success_rate": (hard_success / len(hard)) if hard else 0.0,
        "easy_task_count": len(easy),
        "easy_task_success_count": easy_success,
        "easy_task_success_rate": (easy_success / len(easy)) if easy else 0.0,
        "mean_steps": mean_steps,
        "mean_latency_ms": mean_latency,
    }
