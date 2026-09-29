#!/usr/bin/env python3
"""Compare BEFORE vs AFTER result JSONs and write results/comparison.json."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def pct(x: float) -> str:
    return f"{100.0 * x:.1f}%"


def rel_improvement(before: float, after: float, *, lower_is_better: bool) -> dict:
    if lower_is_better:
        if before == 0:
            delta_pct = 0.0 if after == 0 else float("-inf")
        else:
            delta_pct = 100.0 * (before - after) / before
        ratio = (before / after) if after else float("inf")
    else:
        if before == 0:
            delta_pct = 0.0 if after == 0 else float("inf")
        else:
            delta_pct = 100.0 * (after - before) / before
        ratio = (after / before) if before else float("inf")
    return {"delta_pct": delta_pct, "ratio": ratio}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", type=Path, default=Path("results/before.json"))
    ap.add_argument("--after", type=Path, default=Path("results/after.json"))
    ap.add_argument("--out", type=Path, default=Path("results/comparison.json"))
    args = ap.parse_args()

    before = json.loads(args.before.read_text())
    after = json.loads(args.after.read_text())
    bs, a_s = before["summary"], after["summary"]

    silent_imp = rel_improvement(
        bs["silent_failure_rate"], a_s["silent_failure_rate"], lower_is_better=True
    )
    hallu_imp = rel_improvement(
        bs["hallucinated_tool_result_rate"],
        a_s["hallucinated_tool_result_rate"],
        lower_is_better=True,
    )
    success_imp = rel_improvement(
        bs["task_success_rate"], a_s["task_success_rate"], lower_is_better=False
    )
    hard_imp = rel_improvement(
        bs["hard_task_success_rate"],
        a_s["hard_task_success_rate"],
        lower_is_better=False,
    )

    # Goal checks
    silent_cut_50 = silent_imp["delta_pct"] >= 50.0
    hard_2x = (
        hard_imp["ratio"] >= 2.0
        if bs["hard_task_success_rate"] > 0
        else a_s["hard_task_success_rate"] > bs["hard_task_success_rate"]
    )
    # Also treat 0% → >0% hard success with after >= 50% absolute as a win
    if bs["hard_task_success_rate"] == 0 and a_s["hard_task_success_rate"] >= 0.5:
        hard_2x = True

    goal_met = silent_cut_50 or hard_2x

    comparison = {
        "before_file": str(args.before),
        "after_file": str(args.after),
        "before_summary": bs,
        "after_summary": a_s,
        "improvements": {
            "silent_failure_rate": {
                "before": bs["silent_failure_rate"],
                "after": a_s["silent_failure_rate"],
                **silent_imp,
            },
            "hallucinated_tool_result_rate": {
                "before": bs["hallucinated_tool_result_rate"],
                "after": a_s["hallucinated_tool_result_rate"],
                **hallu_imp,
            },
            "task_success_rate": {
                "before": bs["task_success_rate"],
                "after": a_s["task_success_rate"],
                **success_imp,
            },
            "hard_task_success_rate": {
                "before": bs["hard_task_success_rate"],
                "after": a_s["hard_task_success_rate"],
                **hard_imp,
            },
            "mean_steps": {
                "before": bs["mean_steps"],
                "after": a_s["mean_steps"],
            },
            "mean_latency_ms": {
                "before": bs["mean_latency_ms"],
                "after": a_s["mean_latency_ms"],
            },
        },
        "goals": {
            "silent_failure_reduction_ge_50pct": silent_cut_50,
            "hard_task_success_ge_2x": hard_2x,
            "goal_met": goal_met,
        },
        "per_task": [
            {
                "task_id": b["task_id"],
                "category": b["category"],
                "before_success": b["task_success"],
                "after_success": a["task_success"],
                "before_silent_failure": b["silent_failure"],
                "after_silent_failure": a["silent_failure"],
                "before_hallucinated": b["hallucinated_tool_result"],
                "after_hallucinated": a["hallucinated_tool_result"],
            }
            for b, a in zip(before["scores"], after["scores"])
        ],
    }

    def _sanitize(obj):
        if isinstance(obj, float):
            if obj != obj:  # NaN
                return None
            if obj == float("inf"):
                return "Infinity"
            if obj == float("-inf"):
                return "-Infinity"
            return obj
        if isinstance(obj, dict):
            return {k: _sanitize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_sanitize(v) for v in obj]
        return obj

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(_sanitize(comparison), indent=2) + "\n")

    # Markdown-ish stdout for humans / README
    print("## Agent Reliability — Before vs After\n")
    print("| Metric | BEFORE | AFTER | Δ |")
    print("| --- | ---: | ---: | ---: |")
    print(
        f"| Silent failure rate | {pct(bs['silent_failure_rate'])} "
        f"({bs['silent_failure_count']}/{bs['n_tasks']}) | "
        f"{pct(a_s['silent_failure_rate'])} "
        f"({a_s['silent_failure_count']}/{a_s['n_tasks']}) | "
        f"**−{silent_imp['delta_pct']:.1f}%** |"
    )
    print(
        f"| Hallucinated-tool-result rate | {pct(bs['hallucinated_tool_result_rate'])} | "
        f"{pct(a_s['hallucinated_tool_result_rate'])} | "
        f"**−{hallu_imp['delta_pct']:.1f}%** |"
    )
    print(
        f"| Task success rate | {pct(bs['task_success_rate'])} | "
        f"{pct(a_s['task_success_rate'])} | "
        f"**+{success_imp['delta_pct']:.1f}%** |"
    )
    print(
        f"| Hard-task success rate | {pct(bs['hard_task_success_rate'])} "
        f"({bs['hard_task_success_count']}/{bs['hard_task_count']}) | "
        f"{pct(a_s['hard_task_success_rate'])} "
        f"({a_s['hard_task_success_count']}/{a_s['hard_task_count']}) | "
        f"**×{hard_imp['ratio'] if hard_imp['ratio'] != float('inf') else '∞'}** |"
    )
    print(
        f"| Mean steps | {bs['mean_steps']:.2f} | {a_s['mean_steps']:.2f} | |"
    )
    print(
        f"| Mean latency | {bs['mean_latency_ms']:.1f} ms | "
        f"{a_s['mean_latency_ms']:.1f} ms | |"
    )
    print()
    print(
        f"Goal (≥50% silent-failure cut OR ≥2× hard-task success): "
        f"**{'MET' if goal_met else 'NOT MET'}**"
    )
    print(f"Wrote {args.out}")
    return 0 if goal_met else 2


if __name__ == "__main__":
    raise SystemExit(main())
