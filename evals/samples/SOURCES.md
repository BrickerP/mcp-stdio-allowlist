# Sample sources

`dev.jsonl` and `heldout.jsonl` mix original text and rows adapted from two
public prompt-injection benchmarks (both MIT). Adapted rows keep the original
instruction text and carry the upstream case reference in `adapted_from`.

| source | license | splits | what it is |
|---|---|---|---|
| `hand-written` | `hand-written (original)` | dev (16), held-out (16) | Original prompts and prescribed tool calls. Injection shapes follow this repo's `fixtures/rogue_session.json` (tip/form POST, shell/SQL, URL shortener, token/fee bypass) and the path-prefix failure modes already handled in `src/mcp_stdio_allowlist/policy.py` (traversal, percent-encoding, sibling prefix, NUL). Benign calls match `fixtures/policy.json`: `filesystem.read` under `docs/` and `http.get` GET `api.github.com`. |
| `hand-written (edge)` | `hand-written (original)` | dev (5) | Legitimate-call edge cases that must stay allowed: percent-encoded dot inside `docs/`, lexical `./sub/..` normalize that stays inside `docs/`, allowed host with query string, allowed host with deeper path, lowercase `get` method. |
| `injecagent-dh-base` | MIT (InjecAgent, © 2023 Qiusi Zhan) | held-out (8) | Adapted from [InjecAgent](https://github.com/uiuc-kang-lab/InjecAgent) `data/test_cases_dh_base.json` (commit `f19c9f2c79a41046eb13c03c51a24c567a8ffa07`), cases 34, 136, 170, 255, 289, 357, 374, 408. The attacker instruction text is kept intact; the attacker tool (bank payment, smart-lock/2FA/security-policy action, credential share, profile takeover, repo delete, terminal move) is mapped onto this repo's tool taxonomy (`http_post` / `http.get` / `token_gate_bypass` / `shell_exec`). Exact case and mapping per row in `adapted_from`. |
| `bipia-code-attack` | MIT (BIPIA, © Microsoft Corporation) | held-out (8) | Adapted from [BIPIA](https://github.com/microsoft/BIPIA) `benchmark/code_attack_test.json` (commit `a004b69ec0dd446e0afd461d98cb5e96e120a5d0`), instruction #1 of 8 attack categories (data eavesdropping, keylogging, screen scraping, fingerprinting, OS corruption, ransomware, computer compromise, DoS). The instructed code snippet is kept unmodified and modeled as executed by the agent (`shell_exec`, wrapped in a `python3` heredoc). |

No other public dataset was adapted. Do not invent additional source names.

## Adaptation rules

1. Original instruction text is preserved verbatim inside `input`; the only
   transformation is the tool-call mapping needed to fit this repo's
   `filesystem.read` / `http.get` / `http_post` / `shell_exec` /
   `token_gate_bypass` surface. Mapping notes live in each row's `adapted_from`.
2. Labels are intent labels, not fitted outcomes: injections must be blocked
   under a default-deny allowlist; benign rows must stay allowed. Rows were not
   used to tune the eval policy, and the policy was not changed when they were
   added.
3. Both upstream licenses (MIT) permit adaptation with attribution; commit
   hashes pin the exact upstream revision.

## Split rule

`evals/policy/eval_policy.json` may be tuned **only** against `dev.jsonl`.
Held-out rows exist to measure `block_rate` and `false_block_rate`. Do not
read held-out scores while changing the policy.
