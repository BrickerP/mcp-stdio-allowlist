#!/usr/bin/env python3
"""Run the held-out prompt-injection eval and print block_rate / false_block_rate.

Primary path uses Inspect AI programmatically (no API key: scripted solver).
If inspect-ai is not installed, falls back to the same deterministic scoring
in evals.prompt_injection.score_rows so CI metrics stay defined.

Do not use this output to tune evals/policy/eval_policy.json.
That policy may be tuned only on evals/samples/dev.jsonl.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from evals.prompt_injection import format_report, load_jsonl, score_rows  # noqa: E402
from evals.metrics import block_rate, false_block_rate  # noqa: E402


def _run_inspect(rows: list[dict]) -> bool:
    try:
        from inspect_ai import eval as inspect_eval
        from evals.prompt_injection import prompt_injection
    except Exception as exc:  # ImportError or inspect internals
        print(f"inspect-ai unavailable ({exc.__class__.__name__}: {exc}); using stdlib scorer")
        return False

    logs = inspect_eval(
        prompt_injection(),
        model="mockllm/model",
        display="none",
    )
    if not logs:
        print("inspect eval returned no log; using stdlib scorer")
        return False
    print(f"inspect_log={logs[0].location}")
    # Metrics below are computed from the same guard so the job log is explicit
    # even if Inspect aggregates accuracy rather than the two rates.
    del rows
    return True


def main() -> int:
    heldout = load_jsonl(ROOT / "evals" / "samples" / "heldout.jsonl")
    _run_inspect(heldout)
    on = score_rows(heldout, allowlist_on=True)
    off = score_rows(heldout, allowlist_on=False)
    print(format_report("heldout", heldout))
    print(f"block_rate={block_rate(on):.4f}")
    print(f"false_block_rate={false_block_rate(on):.4f}")
    print(f"baseline_off_block_rate={block_rate(off):.4f}")
    print(f"baseline_off_false_block_rate={false_block_rate(off):.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
