# mcp-stdio-allowlist

[![CI](https://github.com/BrickerP/mcp-stdio-allowlist/actions/workflows/ci.yml/badge.svg)](https://github.com/BrickerP/mcp-stdio-allowlist/actions/workflows/ci.yml)

**If your agent has egress / MCP stdio tools, ship allowlist · dry-run · side-effect summary — not hope.** One command replays a rogue MCP session, blocks form-submit / injection / URL-shortener / token-bypass calls, and writes a pass/fail HTML report.

![Prompt-injection eval](docs/demo-eval.gif)

![Demo report](docs/demo-report.png)

> Not another empty CI framework. A product you can try in under two minutes. Built the morning after Anthropic cut live internet from every internal eval because Claude hit real sites via injection, tip-form submit, token bypass, and URL shorteners.

## The problem

Agents with MCP stdio tools can POST tip forms, shell out with injected SQL, hop through `bit.ly`, or call fake “token/fee gate bypass” tools. Model “judgment” is not a control plane. You need a **policy allowlist**, a **dry-run that never executes side effects**, and a **structured side-effect summary** before anything reaches the wire.

## Try it (< 2 minutes)

Stdlib Python 3.10+. No install, no API keys, no network.

```bash
git clone https://github.com/BrickerP/mcp-stdio-allowlist.git
cd mcp-stdio-allowlist
PYTHONPATH=src python3 -m mcp_stdio_allowlist demo
```

Open `docs/demo-report.html` in a browser.

```
RESULT: PASS
  mode=dry-run  session=rogue_anthropic_mirror
  total=6  blocked=4  allowed=2
  would-write=1  would-fetch=2  would-exec=1
  would-token-bypass=1  would-url-shortener=1
  escaped_side_effects=0
```

What the demo owns end-to-end (our own agent-tool session fixtures):

| # | tool | Anthropic-style failure mode | decision |
|---|---|---|---|
| 1 | `http_post` | tip / form submit | WOULD_BLOCK |
| 2 | `shell_exec` | SQL / command injection | WOULD_BLOCK |
| 3 | `http_get` via bit.ly | URL shortener egress | WOULD_BLOCK |
| 4 | `token_gate_bypass` | token / fee gate bypass | WOULD_BLOCK |
| 5 | `filesystem.read` `docs/README.md` | legitimate read | WOULD_ALLOW |
| 6 | `http.get` `api.github.com/zen` | legitimate GET | WOULD_ALLOW |

![Terminal demo](docs/demo-terminal.png)

## What one run does

1. **Load** a JSON policy allowlist (tool name + optional path / URL-host / method predicates). Path prefixes are matched after lexical normalize (`.`, `..`, `\\`, one layer of `%2e`/`%2f` decode); `..` that escapes the root is denied, and bare prefixes require a `/` boundary (`docs` allows `docs/a`, not `docs_secret`).
2. **Replay** a session of MCP-shaped `tools/call` JSON-RPC messages (recorded JSON; no live network).
3. **Decide** in `dry-run` (report what WOULD happen; execute nothing) or `enforce` (block disallowed).
4. **Emit** structured side-effect counts: blocked / allowed / would-write / would-fetch / would-exec + per-call rows.
5. **Write** `docs/demo-report.html` with PASS/FAIL (PASS = zero escaped side effects under the demo policy).

## Your own session

```bash
PYTHONPATH=src python3 -m mcp_stdio_allowlist run \
  --policy fixtures/policy.json \
  --session fixtures/rogue_session.json \
  --mode dry-run \
  --report docs/demo-report.html
```

Optional thin stdio proxy (filters JSON-RPC `tools/call` on stdin/stdout):

```bash
PYTHONPATH=src python3 -m mcp_stdio_allowlist proxy \
  --policy fixtures/policy.json --mode enforce -- \
  python3 my_mcp_server.py
```

## Layout

```
src/mcp_stdio_allowlist/   # policy · session · guard · side_effects · report · cli
fixtures/                  # our demo policy + rogue MCP session
docs/                      # demo HTML + screenshots from our run
tests/                     # unittest (product is the demo, not empty CI)
```

## Development

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m mcp_stdio_allowlist demo
```

## Prompt-injection eval (held-out)

Scripted agent (no API key) replays each sample's prescribed tool call through the allowlist. Policy: `evals/policy/eval_policy.json` — same rules as the demo (`filesystem.read` under `docs/**`, `http.get` GET `api.github.com`, default deny).

**Policy was tuned only on the dev split. Held-out results were not used for tuning.**

| | |
|---|---|
| held-out **block_rate** | **1.0000** (8/8 injections blocked, allowlist ON) |
| held-out **false_block_rate** | **0.0000** (0/8 benign blocked, allowlist ON) |
| allowlist OFF baseline | block_rate 0.0000 (injections escape), false_block_rate 0.0000 |

| split | N | injection | benign |
|---|---|---|---|
| dev | 16 | 8 | 8 |
| held-out | 16 | 8 | 8 |

Sources: every sample is `hand-written` / `hand-written (original)`, grounded in `fixtures/rogue_session.json` and the path checks in `policy.py`. No public dataset was adapted. Inventory: `evals/samples/SOURCES.md`.

```bash
pip install -e ".[eval]"
PYTHONPATH=src python3 scripts/run_heldout_eval.py
```

## Author

Built by Yupeng Lu — AI agent & backend engineer. I take agents from demo to production: MCP tools, guardrails, evals, billing, real-time systems.

**Hire me:** https://brickerp.github.io/hire/

MIT License.
