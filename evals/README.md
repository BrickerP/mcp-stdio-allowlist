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

## Metrics (allowlist ON)

- **block_rate** — fraction of `label=injection` samples that are blocked.
- **false_block_rate** — fraction of `label=benign` samples that are blocked.

Allowlist OFF is the baseline: every prescribed call is allowed, so injections
escape (`block_rate=0`) and benign calls pass (`false_block_rate=0`).

## How to run

```bash
pip install -e ".[eval]"   # or: pip install inspect-ai
PYTHONPATH=src python3 scripts/run_heldout_eval.py
# Inspect CLI (scripted solver, mockllm, no provider key):
PYTHONPATH=src inspect eval evals/prompt_injection.py
```

If `inspect-ai` is not installed, `scripts/run_heldout_eval.py` still prints the
same rates from the stdlib scorer.

Sources: `samples/SOURCES.md`. All current samples are `hand-written`.
