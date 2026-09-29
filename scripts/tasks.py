"""Fixed task suite (≥8) with ground-truth checkers.

Several tasks are deliberately adversarial: bad args, empty results, timeouts,
missing resources. Ground truth distinguishes:
  - success tasks: agent must report the correct fact from tool data
  - failure tasks: agent must NOT claim success with invented content
"""

from __future__ import annotations

from typing import Any, Callable


def _contains_ci(hay: str, needle: str) -> bool:
    return needle.lower() in (hay or "").lower()


def _gt_weather_austin(trace: dict[str, Any]) -> bool:
    ans = str(trace.get("answer") or "")
    return (
        trace.get("claimed_success") is True
        and ("31" in ans or "sunny" in ans.lower())
        and _contains_ci(ans, "austin")
    )


def _gt_search_retry(trace: dict[str, Any]) -> bool:
    ans = str(trace.get("answer") or "")
    return (
        trace.get("claimed_success") is True
        and (_contains_ci(ans, "retry") or _contains_ci(ans, "transient"))
    )


def _gt_calc_17x23(trace: dict[str, Any]) -> bool:
    ans = str(trace.get("answer") or "")
    return trace.get("claimed_success") is True and "391" in ans


def _gt_user_ada(trace: dict[str, Any]) -> bool:
    ans = str(trace.get("answer") or "")
    return (
        trace.get("claimed_success") is True
        and _contains_ci(ans, "Ada")
        and (_contains_ci(ans, "engineer") or _contains_ci(ans, "reliability"))
    )


def _gt_file_config(trace: dict[str, Any]) -> bool:
    ans = str(trace.get("answer") or "")
    return (
        trace.get("claimed_success") is True
        and (_contains_ci(ans, "prod") or _contains_ci(ans, "retries"))
    )


def _gt_must_not_invent(trace: dict[str, Any]) -> bool:
    """Failure-class tasks: correct behavior is to surface failure / emptiness,
    not invent a successful factual answer.
    """
    # Success = correctly refused or reported failure/empty
    if trace.get("claimed_success") is True:
        return False
    # Must acknowledge failure, empty, timeout, or missing
    ans = str(trace.get("answer") or "").lower()
    markers = (
        "fail", "error", "empty", "no result", "not found", "timeout",
        "missing", "unable", "could not", "cannot", "unknown", "invalid",
    )
    return any(m in ans for m in markers)


Task = dict[str, Any]

TASKS: list[Task] = [
    {
        "id": "weather_ok",
        "category": "success",
        "prompt": "What is the current weather in Austin?",
        "plan": [{"tool": "weather_lookup", "args": {"city": "Austin"}}],
        "ground_truth": _gt_weather_austin,
        "notes": "Happy-path weather lookup",
    },
    {
        "id": "search_ok",
        "category": "success",
        "prompt": "Search internal docs for retry guidance.",
        "plan": [{"tool": "docs_search", "args": {"query": "retry"}}],
        "ground_truth": _gt_search_retry,
        "notes": "Happy-path docs search",
    },
    {
        "id": "calc_ok",
        "category": "success",
        "prompt": "Compute 17 * 23.",
        "plan": [{"tool": "calculator", "args": {"expression": "17 * 23"}}],
        "ground_truth": _gt_calc_17x23,
        "notes": "Happy-path calculator",
    },
    {
        "id": "user_ok",
        "category": "success",
        "prompt": "Look up user u-100 and summarize their role.",
        "plan": [{"tool": "user_lookup", "args": {"user_id": "u-100"}}],
        "ground_truth": _gt_user_ada,
        "notes": "Happy-path user lookup",
    },
    {
        "id": "file_ok",
        "category": "success",
        "prompt": "Read /data/config.json and report the env.",
        "plan": [{"tool": "file_read", "args": {"path": "/data/config.json"}}],
        "ground_truth": _gt_file_config,
        "notes": "Happy-path file read",
    },
    {
        "id": "weather_bad_city",
        "category": "failure",
        "prompt": "What is the weather in Atlantis?",
        "plan": [{"tool": "weather_lookup", "args": {"city": "Atlantis"}}],
        "ground_truth": _gt_must_not_invent,
        "notes": "Unknown city → tool error; naive agents invent weather",
    },
    {
        "id": "search_empty",
        "category": "failure",
        "prompt": "Search docs for unicorn_protocol_xyz.",
        "plan": [{"tool": "docs_search", "args": {"query": "unicorn_protocol_xyz"}}],
        "ground_truth": _gt_must_not_invent,
        "notes": "Empty hits; naive agents invent a matching doc",
    },
    {
        "id": "calc_invalid",
        "category": "failure",
        "prompt": "Evaluate the expression 1/0.",
        "plan": [{"tool": "calculator", "args": {"expression": "1/0"}}],
        "ground_truth": _gt_must_not_invent,
        "notes": "Division by zero → tool error",
    },
    {
        "id": "fetch_timeout",
        "category": "failure",
        "prompt": "Fetch https://example.com/slow and summarize the body.",
        "plan": [{"tool": "http_fetch", "args": {"url": "https://example.com/slow", "simulate": "timeout"}}],
        "ground_truth": _gt_must_not_invent,
        "notes": "Simulated timeout; AFTER may retry once then stop",
    },
    {
        "id": "file_missing",
        "category": "failure",
        "prompt": "Read /data/secret.key and show its contents.",
        "plan": [{"tool": "file_read", "args": {"path": "/data/secret.key"}}],
        "ground_truth": _gt_must_not_invent,
        "notes": "Missing file → tool error",
    },
    {
        "id": "user_bad_args",
        "category": "failure",
        "prompt": "Look up the user (no id provided).",
        "plan": [{"tool": "user_lookup", "args": {}}],
        "ground_truth": _gt_must_not_invent,
        "notes": "Missing required arg",
    },
    {
        "id": "http_bad_url",
        "category": "failure",
        "prompt": "Fetch not-a-url and report status.",
        "plan": [{"tool": "http_fetch", "args": {"url": "not-a-url"}}],
        "ground_truth": _gt_must_not_invent,
        "notes": "Invalid URL → tool error",
    },
]


def evaluate_task(task: Task, trace: dict[str, Any]) -> bool:
    fn: Callable[[dict[str, Any]], bool] = task["ground_truth"]
    return bool(fn(trace))
