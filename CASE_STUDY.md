# Case Study: Before & After Agent Reliability

**Repository:** https://github.com/oligotsol/agent-reliability-before-after  
**Author:** oli (oligotsol)  
**Measured:** 2026-09-28 (America/Chicago)  
**Stack:** Python 3.13 stdlib harness · mocked tools · deterministic LLM-stub planner · CPU only  
**Series:** Second public case study after [llm-inference-before-after](https://github.com/oligotsol/llm-inference-before-after)

---

## Executive summary

Tool-using LLM agents fail in ways that benchmarks rarely catch: they **claim success when a tool failed**, **invent a tool payload**, or **skip verification** and keep talking. We built a fixed task suite that forces those failure modes, ran a **naive** agent loop (BEFORE), then the same tasks through a **verified-trace** loop (AFTER).

| Metric | BEFORE (naive) | AFTER (verified) | Improvement |
| --- | ---: | ---: | ---: |
| Silent failure rate | 58.3% (7/12) | 0.0% (0/12) | **100% reduction** |
| Hallucinated-tool-result rate | 58.3% (7/12) | 0.0% (0/12) | **100% reduction** |
| Task success rate | 41.7% (5/12) | 100% (12/12) | **+140%** |
| Hard-task success rate | 0% (0/7) | 100% (7/7) | **0 → 7 tasks** |
| Mean steps | 1.58 | 2.67 | +verification steps |
| Mean latency | 8.4 ms | 10.5 ms | +~2 ms (mock I/O) |

**Success criteria:** ≥50% silent-failure reduction **or** ≥2× hard-task success.  
**Result:** **Both** — silent failures eliminated; hard-task success from 0/7 to 7/7.

All numbers below come from committed JSON under `results/` produced by `scripts/bench.py` on this machine. Nothing was invented.

---

## Problem: silent failures in tool-using agents

A growing share of “AI systems” work is not raw token generation — it is **agents that call tools**. The industry pain is specific:

1. **Silent failure** — the tool returned an error / empty payload; the agent still answered as if it worked.
2. **Hallucinated tool results** — the transcript contains a tool “observation” that was never returned by the tool.
3. **No verification** — no schema check, no retry/stop policy, no faithfulness check against actual tool outputs.

These bugs look like confidence. They ship. This case study isolates them with a reproducible harness.

Positioning relative to the first case study ([llm-inference-before-after](https://github.com/oligotsol/llm-inference-before-after)): that repo proved measurement discipline on **inference efficiency**. This one proves the same discipline on **agent correctness under tool failure** — a different axis of next-gen contributor credibility.

---

## Pipeline

```
Fixed task suite (12 prompts)
        │
        ├─► BEFORE: naive loop
        │     plan → call tool → IGNORE ok/error/empty
        │                      → invent success answer + fake tool row
        │
        └─► AFTER: verified loop
              plan → call tool → schema-check envelope+payload
                               → empty-result gate
                               → retry once on transient timeout, else stop
                               → compose answer ONLY from verified payloads
                               → faithfulness gate
        │
        ▼
   metrics.py  →  silent failure / hallucination / ground-truth success
        │
        ▼
   results/{before,after,comparison}.json
```

Why a stub planner + mocked tools:

- **Reproducible on CPU** with no GPU, no Hugging Face download, no paid API key.
- Metrics still measure **real control-flow behavior** of the harness (does the agent invent? does it stop? does ground truth pass?).
- Failure modes (timeout, empty, bad args, missing resource) are **deterministic**, so before/after deltas are attributable to verification — not to model sampling noise.

---

## Techniques applied (AFTER)

### 1. Schema-checked tool results

Every tool return must pass:

- A shared **envelope** (`ok`, `error`, `data`, `latency_ms`, `tool`, `args`)
- A **per-tool payload** schema (e.g. weather requires `city` / `temp_c` / `condition`; docs requires `hits` with `count == len(hits)`)

Invalid envelopes stop the loop. No answer is composed from garbage.

### 2. Failure surfacing

`ok: false` becomes an explicit stop answer naming the tool and error. The agent **does not** claim success.

### 3. Empty-result handling

`ok: true` with zero docs hits (or empty body) is treated as a **non-answer**. Naive loops often invent a “matching” document here — that is counted as both silent failure and hallucination.

### 4. Retry / stop rules

Transient failures (`error: timeout`, flagged `transient: true`) get **one** retry. A second timeout stops. Permanent errors (unknown city, missing file, bad URL, missing args) do not retry.

### 5. Faithfulness gate

A claimed success requires at least one **verified** payload in the trace. Answers matching known fabrication patterns fail the gate. This is a lightweight, deterministic stand-in for an LLM-as-judge faithfulness scorer — same *role*, no API cost.

---

## Task suite

Twelve fixed tasks in `scripts/tasks.py`:

| ID | Category | Tool stress |
| --- | --- | --- |
| `weather_ok` | success | Valid city |
| `search_ok` | success | Query with hits |
| `calc_ok` | success | `17 * 23` → 391 |
| `user_ok` | success | Known `u-100` |
| `file_ok` | success | Existing config path |
| `weather_bad_city` | failure | Unknown city |
| `search_empty` | failure | Zero hits |
| `calc_invalid` | failure | `1/0` |
| `fetch_timeout` | failure | Simulated timeout |
| `file_missing` | failure | Missing path |
| `user_bad_args` | failure | Missing `user_id` |
| `http_bad_url` | failure | Invalid URL |

Ground-truth checkers:

- **Success tasks** — answer must contain the real tool fact and `claimed_success=true`.
- **Failure tasks** — agent must **not** claim success; answer must acknowledge failure / empty / timeout / missing.

---

## Metric definitions

| Metric | Definition |
| --- | --- |
| **Silent failure** | `claimed_success=true` while any real tool call failed, returned empty, or the agent injected / invented a tool result |
| **Hallucinated-tool-result** | Trace contains an injected fake tool row, or `invented_answer=true`, or AFTER faithfulness gate failed |
| **Task success** | Task-specific ground-truth checker returns true |
| **Hard-task success** | Task success restricted to `category=failure` |
| **Mean steps / latency** | Average control-flow steps and wall time per task |

---

## Hardware under test

Captured by `scripts/bench.py` and embedded in each results JSON:

| Field | Value |
| --- | --- |
| OS / kernel | Linux 6.12.94+ x86_64 |
| CPU | Intel Xeon (8 logical CPUs) |
| RAM | ~15 GiB |
| Python | 3.13.5 |
| GPU / CUDA | **None** |
| External APIs | **None** |
| Model weights | **None** (deterministic stub planner) |

---

## Results

### Headline comparison

From `results/comparison.json` (regenerated by `scripts/compare.py`):

| Metric | BEFORE | AFTER | Δ |
| --- | ---: | ---: | ---: |
| Silent failure rate | 58.3% (7/12) | 0.0% (0/12) | **−100%** |
| Hallucinated-tool-result rate | 58.3% | 0.0% | **−100%** |
| Task success rate | 41.7% | 100% | **+140%** |
| Hard-task success | 0/7 | 7/7 | **fixed all adversarial tasks** |
| Mean steps | 1.58 | 2.67 | schema + gate steps |
| Mean latency | 8.4 ms | 10.5 ms | retry on timeout path |

### Per-task matrix

| Task | BEFORE success | AFTER success | BEFORE silent | AFTER silent |
| --- | :---: | :---: | :---: | :---: |
| weather_ok | ✓ | ✓ | | |
| search_ok | ✓ | ✓ | | |
| calc_ok | ✓ | ✓ | | |
| user_ok | ✓ | ✓ | | |
| file_ok | ✓ | ✓ | | |
| weather_bad_city | ✗ | ✓ | silent+hallu | |
| search_empty | ✗ | ✓ | silent+hallu | |
| calc_invalid | ✗ | ✓ | silent+hallu | |
| fetch_timeout | ✗ | ✓ | silent+hallu | |
| file_missing | ✗ | ✓ | silent+hallu | |
| user_bad_args | ✗ | ✓ | silent+hallu | |
| http_bad_url | ✗ | ✓ | silent+hallu | |

Happy-path quality is preserved (5/5 → 5/5). All gains are on the adversarial set — exactly where naive loops look “helpful” and are wrong.

### What BEFORE did wrong (examples)

- **Unknown city** → invented “72°F and partly cloudy” and injected a fake successful weather payload.
- **Empty docs search** → invented “Unicorn Protocol Overview”.
- **Timeout** → claimed HTTP 200 OK without a real body.
- **Missing file** → returned a placeholder “secret”.

### What AFTER did instead

- Surfaced `unknown_city:Atlantis`, `file_not_found`, `invalid_url`, missing args.
- Treated empty docs as non-answer.
- Retried timeout once, then stopped with an explicit timeout message.
- Never set `claimed_success` without a verified payload.

---

## Reproduce

```bash
git clone https://github.com/oligotsol/agent-reliability-before-after.git
cd agent-reliability-before-after
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt   # stdlib-only today

python scripts/bench.py --mode before --out results/before.json
python scripts/bench.py --mode after  --out results/after.json
python scripts/compare.py
```

Expect deterministic totals matching the committed JSON (tool sleeps are fixed; no RNG in the planner).

---

## Honest limits

1. **Stub planner, not a frontier LLM.** The case study measures verification *machinery* and failure taxonomy, not whether GPT/Claude/Qwen would invent on these prompts. Real models may invent less — or more cleverly. The AFTER gates still apply.
2. **Mocked tools.** Deterministic timeouts / empty / not-found. Production adds partial failures, auth errors, schema drift, and race conditions. The same envelope + retry + faithfulness pattern extends; the absolute rates will differ.
3. **Rule-based faithfulness.** Markers + “must have verified payload” is a lower bound on a full LLM-as-judge. It is also free, deterministic, and sufficient to catch every BEFORE fabrication in this suite.
4. **Latency is not the point.** Mock I/O is milliseconds. In production, verification overhead is dominated by extra tool round-trips on retry — still cheap vs a silent wrong action.
5. **Not a claim about all agent frameworks.** This is a controlled before/after on a published harness, not a survey of LangChain/LlamaIndex/etc.

---

## Why this signals next-gen credibility

Future AI systems problems are less “make the model smaller” and more “make the system trustworthy when tools disagree with the narrative.” This repo shows:

- **Problem selection** — silent tool failure is an industry-relevant reliability class.
- **Measurement discipline** — fixed suite, named metrics, committed JSON, reproduce script.
- **Remediation that moves the metric** — not a vibes write-up; −100% silent failures with preserved happy-path success.
- **Honest limits** — stub/mocked scope stated up front.

Together with [llm-inference-before-after](https://github.com/oligotsol/llm-inference-before-after), the public trail covers **efficiency** and **agent reliability** — two axes hiring managers and research collaborators actually stress.

---

## License

MIT — see [LICENSE](./LICENSE).
