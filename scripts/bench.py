#!/usr/bin/env python3
"""Run the fixed task suite under BEFORE or AFTER agent mode.

Usage:
  python scripts/bench.py --mode before --out results/before.json
  python scripts/bench.py --mode after  --out results/after.json
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Allow `python scripts/bench.py` from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent))

import agent_after
import agent_before
from metrics import aggregate, score_trace
from tasks import TASKS


def hardware_snapshot() -> dict:
    info = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "processor": platform.processor() or platform.machine(),
        "nproc": os.cpu_count(),
        "gpu": "none (CPU-only harness)",
    }
    try:
        mem = subprocess.check_output(["free", "-m"], text=True)
        for line in mem.splitlines():
            if line.lower().startswith("mem:"):
                parts = line.split()
                info["ram_total_mb"] = int(parts[1])
                break
    except Exception:  # noqa: BLE001
        info["ram_total_mb"] = None
    try:
        cpu = subprocess.check_output(
            ["bash", "-lc", "grep -m1 'model name' /proc/cpuinfo | cut -d: -f2"],
            text=True,
        ).strip()
        if cpu:
            info["cpu_model"] = cpu
    except Exception:  # noqa: BLE001
        pass
    return info


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mode", choices=("before", "after"), required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=0, help="Reserved for future stub RNG")
    args = ap.parse_args()

    runner = agent_before.run_task if args.mode == "before" else agent_after.run_task
    started = time.perf_counter()
    traces = []
    scores = []

    for task in TASKS:
        trace = runner(task)
        sc = score_trace(task, trace)
        traces.append(trace)
        scores.append(sc)
        flag = "OK" if sc["task_success"] else "FAIL"
        silent = " SILENT" if sc["silent_failure"] else ""
        hallu = " HALLU" if sc["hallucinated_tool_result"] else ""
        print(
            f"[{args.mode}] {task['id']:16s}  {flag:4s}{silent}{hallu}  "
            f"steps={sc['n_steps']}  {sc['elapsed_ms']:.1f}ms  "
            f"ans={str(sc['answer'])[:70]!r}"
        )

    summary = aggregate(scores)
    wall_ms = (time.perf_counter() - started) * 1000.0

    payload = {
        "label": args.mode,
        "mode": args.mode,
        "measured_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "measured_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "hardware": hardware_snapshot(),
        "n_tasks": len(TASKS),
        "task_ids": [t["id"] for t in TASKS],
        "summary": summary,
        "scores": scores,
        "traces": traces,
        "wall_ms": wall_ms,
        "notes": (
            "Deterministic LLM-stub + mocked tools. Metrics reflect real harness "
            "behavior (silent failures, hallucinations, ground-truth task success), "
            "not invented numbers."
        ),
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, default=str) + "\n")
    print(f"\nWrote {args.out}")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
