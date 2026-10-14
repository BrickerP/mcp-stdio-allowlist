# Sample sources

Every row in `dev.jsonl` and `heldout.jsonl` is original text written for this
repository. None were copied from a public prompt-injection benchmark.

| source | license | splits | what it is |
|---|---|---|---|
| `hand-written` | `hand-written (original)` | dev (16), held-out (16) | Original prompts and prescribed tool calls. Injection shapes follow this repo's `fixtures/rogue_session.json` (tip/form POST, shell/SQL, URL shortener, token/fee bypass) and the path-prefix failure modes already handled in `src/mcp_stdio_allowlist/policy.py` (traversal, percent-encoding, sibling prefix, NUL). Benign calls match `fixtures/policy.json`: `filesystem.read` under `docs/` and `http.get` GET `api.github.com`. |

No public dataset was adapted. Do not invent additional source names.

## Split rule

`evals/policy/eval_policy.json` may be tuned **only** against `dev.jsonl`.
Held-out rows exist to measure `block_rate` and `false_block_rate`. Do not
read held-out scores while changing the policy.
