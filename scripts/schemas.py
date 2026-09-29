"""JSON-Schema-like validators for tool results (stdlib only, no jsonschema dep).

AFTER agent uses these to reject malformed / incomplete tool envelopes before
they enter the answer-composition step.
"""

from __future__ import annotations

from typing import Any


REQUIRED_ENVELOPE = ("ok", "error", "data", "latency_ms", "tool", "args")


def validate_envelope(result: Any) -> tuple[bool, str | None]:
    if not isinstance(result, dict):
        return False, "result_not_object"
    for key in REQUIRED_ENVELOPE:
        if key not in result:
            return False, f"missing_envelope_field:{key}"
    if not isinstance(result["ok"], bool):
        return False, "ok_not_bool"
    if result["ok"] is False and not result.get("error"):
        return False, "failed_without_error"
    if result["ok"] is True and result.get("error") not in (None, ""):
        return False, "ok_with_error_set"
    return True, None


def validate_payload(tool: str, result: dict[str, Any]) -> tuple[bool, str | None]:
    """Schema-check successful payloads per tool. Failures skip payload checks."""
    ok_env, err = validate_envelope(result)
    if not ok_env:
        return False, err
    if not result["ok"]:
        return True, None  # failure envelope is valid; payload may be null

    data = result.get("data")
    if data is None:
        return False, "ok_with_null_data"

    if tool == "weather_lookup":
        for k in ("city", "temp_c", "condition"):
            if k not in data:
                return False, f"weather_missing:{k}"
        if not isinstance(data["temp_c"], (int, float)):
            return False, "weather_temp_not_number"
    elif tool == "docs_search":
        if "hits" not in data or "count" not in data:
            return False, "docs_missing_hits_or_count"
        if not isinstance(data["hits"], list):
            return False, "docs_hits_not_list"
        if data["count"] != len(data["hits"]):
            return False, "docs_count_mismatch"
    elif tool == "calculator":
        if "value" not in data:
            return False, "calc_missing_value"
    elif tool == "user_lookup":
        for k in ("user_id", "name", "role"):
            if k not in data:
                return False, f"user_missing:{k}"
    elif tool == "file_read":
        for k in ("path", "content"):
            if k not in data:
                return False, f"file_missing:{k}"
    elif tool == "http_fetch":
        for k in ("url", "status", "body"):
            if k not in data:
                return False, f"http_missing:{k}"
    return True, None


def is_empty_success(tool: str, result: dict[str, Any]) -> bool:
    """True when the tool 'succeeded' but produced no usable content."""
    if not result.get("ok"):
        return False
    data = result.get("data") or {}
    if tool == "docs_search":
        return int(data.get("count") or 0) == 0
    if tool == "file_read":
        return not (data.get("content") or "").strip()
    if tool == "http_fetch":
        return not (data.get("body") or "").strip()
    return False
