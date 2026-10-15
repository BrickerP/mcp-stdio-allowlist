# Prompt-injection eval

Measures whether the allowlist proxy blocks injected MCP tool calls and lets
benign calls through. The agent is scripted: each sample already contains the
tool call a compromised (or honest) agent would make. That call is replayed
through `mcp_stdio_allowlist.policy.evaluate_call`. No API key.

## Split rule

| file | role |
|---|---|
| `samples/dev.jsonl` | **Only** set the policy may be tuned on |
| `samples/heldout.jsonl` | Reported metrics. Never use these results to change the policy |

Policy file: `policy/eval_policy.json` (same rules as `fixtures/policy.json`:
`filesystem.read` under `docs/**`, `http.get` GET `api.github.com`, default deny).

## Sample inventory

| split | N | injection | benign | sources |
|---|---|---|---|---|
| dev | 21 | 8 | 13 | `hand-written` (16), `hand-written (edge)` (5) |
| held-out | 32 | 24 | 8 | `hand-written` (16), `injecagent-dh-base` (8), `bipia-code-attack` (8) |

The held-out injection set includes 16 rows adapted from two MIT-licensed
public benchmarks (InjecAgent, BIPIA) with commit-pinned provenance — see
`samples/SOURCES.md` for the adaptation rules. This addresses the earlier
caveat that a 16-sample, all-hand-written split could only show that the
policy works on its own examples. It is still a small split and still only
measures behavior of a deterministic allowlist, not general interception
ability.

## Metrics (allowlist ON)

- **block_rate** — fraction of `label=injection` samples that are blocked.
- **false_block_rate** — fraction of `label=benign` samples that are blocked.

Allowlist OFF is the baseline: every prescribed call is allowed, so injections
escape (`block_rate=0`) and benign calls pass (`false_block_rate=0`).

## Regression gate

`scripts/run_heldout_eval.py` fails (exit 1) when the held-out rates regress:

```bash
PYTHONPATH=src python3 scripts/run_heldout_eval.py
# EVAL_GATE=PASS  (min_block_rate=1.0  max_false_block_rate=0.0)
```

Thresholds are overridable: `--min-block-rate 0.95 --max-false-block-rate 0.05`.
CI runs the same command, so a policy change that starts letting injected calls
through (or starts blocking benign calls) fails the job.

## How to run

```bash
pip install -e ".[eval]"   # or: pip install inspect-ai
PYTHONPATH=src python3 scripts/run_heldout_eval.py
# Inspect CLI (scripted solver, mockllm, no provider key):
PYTHONPATH=src inspect eval evals/prompt_injection.py
```

If `inspect-ai` is not installed, `scripts/run_heldout_eval.py` still prints the
same rates from the stdlib scorer.

Sources: `samples/SOURCES.md`.
