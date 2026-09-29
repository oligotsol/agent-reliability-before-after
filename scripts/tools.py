"""Mocked tools for the agent reliability harness.

Each tool returns a structured dict with:
  ok: bool
  error: optional str
  data: optional payload
  latency_ms: simulated wall time applied via time.sleep

Failures are deterministic for fixed task args (empty results, bad args,
timeouts, missing resources).
"""

from __future__ import annotations

import time
from typing import Any

# Simulated "backend" data
_WEATHER = {
    "austin": {"city": "Austin", "temp_c": 31, "condition": "sunny", "humidity": 48},
    "chicago": {"city": "Chicago", "temp_c": 18, "condition": "cloudy", "humidity": 62},
    "seattle": {"city": "Seattle", "temp_c": 14, "condition": "rain", "humidity": 78},
}

_DOCS = [
    {"id": "doc-1", "title": "Retry policies", "snippet": "Retry transient timeouts once, then stop."},
    {"id": "doc-2", "title": "Schema validation", "snippet": "Validate tool results against JSON Schema."},
    {"id": "doc-3", "title": "Faithfulness judges", "snippet": "Score answers against actual tool outputs."},
]

_USERS = {
    "u-100": {"user_id": "u-100", "name": "Ada Lovelace", "role": "engineer", "team": "reliability"},
    "u-200": {"user_id": "u-200", "name": "Grace Hopper", "role": "architect", "team": "platform"},
}

_FILES = {
    "/data/config.json": '{"env": "prod", "retries": 1}',
    "/data/readme.txt": "Agent reliability harness sample file.",
}


def _sleep_ms(ms: float) -> None:
    if ms > 0:
        time.sleep(ms / 1000.0)


def weather_lookup(city: str | None = None, **_extra: Any) -> dict[str, Any]:
    t0 = time.perf_counter()
    _sleep_ms(8)
    if not city or not isinstance(city, str):
        return {
            "ok": False,
            "error": "missing_required_arg:city",
            "data": None,
            "latency_ms": (time.perf_counter() - t0) * 1000,
        }
    key = city.strip().lower()
    if key not in _WEATHER:
        return {
            "ok": False,
            "error": f"unknown_city:{city}",
            "data": None,
            "latency_ms": (time.perf_counter() - t0) * 1000,
        }
    return {
        "ok": True,
        "error": None,
        "data": dict(_WEATHER[key]),
        "latency_ms": (time.perf_counter() - t0) * 1000,
    }


def docs_search(query: str | None = None, **_extra: Any) -> dict[str, Any]:
    t0 = time.perf_counter()
    _sleep_ms(10)
    if not query or not isinstance(query, str):
        return {
            "ok": False,
            "error": "missing_required_arg:query",
            "data": None,
            "latency_ms": (time.perf_counter() - t0) * 1000,
        }
    q = query.strip().lower()
    hits = [d for d in _DOCS if q in d["title"].lower() or q in d["snippet"].lower()]
    # Explicit empty-result queries used by the task suite
    if q in {"zzzz_no_match", "unicorn_protocol_xyz"}:
        hits = []
    return {
        "ok": True,
        "error": None,
        "data": {"query": query, "hits": hits, "count": len(hits)},
        "latency_ms": (time.perf_counter() - t0) * 1000,
    }


def calculator(expression: str | None = None, **_extra: Any) -> dict[str, Any]:
    t0 = time.perf_counter()
    _sleep_ms(3)
    if not expression or not isinstance(expression, str):
        return {
            "ok": False,
            "error": "missing_required_arg:expression",
            "data": None,
            "latency_ms": (time.perf_counter() - t0) * 1000,
        }
    expr = expression.strip()
    # Extremely small safe eval: digits, + - * / ( ) . and spaces only
    allowed = set("0123456789+-*/(). ")
    if not set(expr) <= allowed:
        return {
            "ok": False,
            "error": f"invalid_expression:{expression}",
            "data": None,
            "latency_ms": (time.perf_counter() - t0) * 1000,
        }
    try:
        value = eval(expr, {"__builtins__": {}}, {})  # noqa: S307 — intentionally restricted
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "error": f"eval_error:{type(exc).__name__}:{exc}",
            "data": None,
            "latency_ms": (time.perf_counter() - t0) * 1000,
        }
    if isinstance(value, float) and (value != value or value in (float("inf"), float("-inf"))):
        return {
            "ok": False,
            "error": "non_finite_result",
            "data": None,
            "latency_ms": (time.perf_counter() - t0) * 1000,
        }
    return {
        "ok": True,
        "error": None,
        "data": {"expression": expression, "value": value},
        "latency_ms": (time.perf_counter() - t0) * 1000,
    }


def user_lookup(user_id: str | None = None, **_extra: Any) -> dict[str, Any]:
    t0 = time.perf_counter()
    _sleep_ms(6)
    if not user_id or not isinstance(user_id, str):
        return {
            "ok": False,
            "error": "missing_required_arg:user_id",
            "data": None,
            "latency_ms": (time.perf_counter() - t0) * 1000,
        }
    if user_id not in _USERS:
        return {
            "ok": False,
            "error": f"user_not_found:{user_id}",
            "data": None,
            "latency_ms": (time.perf_counter() - t0) * 1000,
        }
    return {
        "ok": True,
        "error": None,
        "data": dict(_USERS[user_id]),
        "latency_ms": (time.perf_counter() - t0) * 1000,
    }


def file_read(path: str | None = None, **_extra: Any) -> dict[str, Any]:
    t0 = time.perf_counter()
    _sleep_ms(4)
    if not path or not isinstance(path, str):
        return {
            "ok": False,
            "error": "missing_required_arg:path",
            "data": None,
            "latency_ms": (time.perf_counter() - t0) * 1000,
        }
    if path not in _FILES:
        return {
            "ok": False,
            "error": f"file_not_found:{path}",
            "data": None,
            "latency_ms": (time.perf_counter() - t0) * 1000,
        }
    return {
        "ok": True,
        "error": None,
        "data": {"path": path, "content": _FILES[path]},
        "latency_ms": (time.perf_counter() - t0) * 1000,
    }


def http_fetch(url: str | None = None, simulate: str | None = None, **_extra: Any) -> dict[str, Any]:
    """Mock HTTP fetch. Use simulate='timeout' to force a timeout failure."""
    t0 = time.perf_counter()
    if simulate == "timeout":
        _sleep_ms(25)
        return {
            "ok": False,
            "error": "timeout",
            "data": None,
            "latency_ms": (time.perf_counter() - t0) * 1000,
            "transient": True,
        }
    _sleep_ms(12)
    if not url or not isinstance(url, str):
        return {
            "ok": False,
            "error": "missing_required_arg:url",
            "data": None,
            "latency_ms": (time.perf_counter() - t0) * 1000,
        }
    if not url.startswith(("http://", "https://")):
        return {
            "ok": False,
            "error": f"invalid_url:{url}",
            "data": None,
            "latency_ms": (time.perf_counter() - t0) * 1000,
        }
    # Deterministic fake payload keyed by URL path
    body = {"url": url, "status": 200, "body": f"OK payload for {url}"}
    return {
        "ok": True,
        "error": None,
        "data": body,
        "latency_ms": (time.perf_counter() - t0) * 1000,
    }


TOOL_REGISTRY: dict[str, Any] = {
    "weather_lookup": weather_lookup,
    "docs_search": docs_search,
    "calculator": calculator,
    "user_lookup": user_lookup,
    "file_read": file_read,
    "http_fetch": http_fetch,
}


def call_tool(name: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
    """Dispatch a tool call. Unknown tools return a structured error."""
    args = args or {}
    fn = TOOL_REGISTRY.get(name)
    if fn is None:
        return {
            "ok": False,
            "error": f"unknown_tool:{name}",
            "data": None,
            "latency_ms": 0.0,
        }
    result = fn(**args)
    result["tool"] = name
    result["args"] = dict(args)
    return result
