# Agent Reliability Before & After

**Real measured case study:** stop silent tool-use failures in LLM agents with verified traces — schema checks, failure surfacing, retry/stop rules, and a faithfulness gate. Not another quantization bench.

| | BEFORE (naive loop) | AFTER (verified traces) | Δ |
| --- | ---: | ---: | ---: |
| **Silent failure rate** | **58.3%** (7/12) | **0.0%** (0/12) | **−100%** |
| **Hallucinated-tool-result rate** | 58.3% (7/12) | 0.0% (0/12) | **−100%** |
| **Task success rate** | 41.7% (5/12) | 100% (12/12) | **+140%** |
| **Hard-task success** | 0% (0/7) | 100% (7/7) | **0 → 7** |
| Mean steps / latency | 1.58 · 8.4 ms | 2.67 · 10.5 ms | verification overhead |

**Goal met:** ≥50% silent-failure reduction **and** dramatically better hard-task success (empty results, timeouts, bad args, missing resources).

This is Oli’s **second** public before/after case study (after [llm-inference-before-after](https://github.com/oligotsol/llm-inference-before-after)). Theme: the industry pain of tool-using agents that **claim success when tools failed**, **invent tool results**, or **skip verification**.

Stack: stdlib-only Python harness · mocked tools · deterministic LLM-stub modes (clearly labeled) · CPU, no GPU, no paid APIs. Metrics measure **real harness behavior**, not invented scores.

Full narrative, tables, and reproduce steps → **[CASE_STUDY.md](./CASE_STUDY.md)** · raw JSON → [`results/`](./results/).

---

## Why this matters for future agent systems

Quantization and latency matter. So does **whether the agent is telling the truth about what its tools did**.

Production agent stacks (tool routers, ReAct loops, multi-step planners) routinely:

1. Ignore `ok` / HTTP / empty-result signals and keep generating.
2. Invent a plausible tool payload when parsing fails.
3. Skip schema validation on tool envelopes.
4. Lack a stop rule when retries are exhausted.

Those failure modes do not show up on MMLU. They show up as **silent failures** — the agent reports success while the world disagreed. This repo isolates that failure class and measures a remediation.

---

## Quick start

```bash
git clone https://github.com/oligotsol/agent-reliability-before-after.git
cd agent-reliability-before-after

python3 -m venv .venv
source .venv/bin/activate
# stdlib-only; requirements.txt documents the empty pin set
pip install -r requirements.txt   # no-op today

# BEFORE — naive tool-use loop
python scripts/bench.py --mode before --out results/before.json

# AFTER — verified traces
python scripts/bench.py --mode after --out results/after.json

python scripts/compare.py
```

Re-runs are deterministic for a given task suite (mocked tools + stub planner).

---

## What’s in the repo

| Path | Purpose |
| --- | --- |
| `scripts/tools.py` | Mocked tools (weather, docs, calc, user, file, HTTP) with real fail modes |
| `scripts/schemas.py` | Envelope + per-tool payload validation |
| `scripts/tasks.py` | Fixed ≥8-task suite (5 success + 7 adversarial) + ground-truth checkers |
| `scripts/agent_before.py` | Naive loop: ignores failures, invents results |
| `scripts/agent_after.py` | Verified loop: schema · empty · retry/stop · faithfulness |
| `scripts/metrics.py` | Silent failure / hallucination / task-success definitions |
| `scripts/bench.py` | Run suite under `--mode before\|after` |
| `scripts/compare.py` | Markdown + `results/comparison.json` |
| `results/*.json` | **Committed** measurements from this machine |
| `CASE_STUDY.md` | Full write-up: problem, pipeline, techniques, limits |

---

## Techniques (AFTER)

1. **Schema-checked tool results** — reject malformed envelopes / payloads before answer composition.
2. **Failure surfacing** — tool errors become explicit stop answers; never invent success.
3. **Empty-result handling** — `ok:true` with zero hits is treated as non-answer.
4. **Retry/stop rules** — one retry on transient timeouts, then stop.
5. **Faithfulness gate** — success requires a verified payload; fabrication markers fail the gate.

---

## Measurement protocol (summary)

- Fixed suite of **12 tasks** (5 happy-path, 7 designed to fail)
- Same tools, same prompts, BEFORE vs AFTER
- Metrics: silent failure rate, hallucinated-tool-result rate, task success (ground truth), hard-task success, mean steps, mean latency
- Hardware: CPU-only box, no GPU; stub LLM + mocked tools so anyone can reproduce without API keys

---

## Honest limits

- Planner is a **deterministic stub**, not a frontier model — the case study measures verification machinery, not raw model IQ.
- Tools are **mocked** (deterministic fail/success). Real HTTP/DB flakiness is wider; the patterns transfer.
- Faithfulness gate here is rule-based (payload grounding + fabrication markers), not an LLM-as-judge.

See [CASE_STUDY.md](./CASE_STUDY.md) for full caveats.

---

MIT · oli (oligotsol) · measured 2026-09-28
