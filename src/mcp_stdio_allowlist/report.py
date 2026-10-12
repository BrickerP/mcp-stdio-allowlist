"""Emit HTML side-effect summary report."""
from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .guard import GuardSummary


def _esc(x: Any) -> str:
    return html.escape(str(x))


def write_report(summary: GuardSummary, out_path: Path, title: str = "mcp-stdio-allowlist report") -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    overall = "PASS" if summary.passed else "FAIL"
    overall_cls = "pass" if summary.passed else "fail"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    rows_html = []
    for r in summary.rows:
        mark = r.decision
        cls = "pass" if r.decision in ("ALLOWED", "WOULD_ALLOW") and not r.escaped else "fail"
        if r.decision in ("BLOCKED", "WOULD_BLOCK"):
            cls = "block"
        args_s = json.dumps(r.arguments, ensure_ascii=False)
        if len(args_s) > 120:
            args_s = args_s[:117] + "..."
        rows_html.append(
            f"<tr class='{cls}'>"
            f"<td><code>{_esc(r.id)}</code></td>"
            f"<td><code>{_esc(r.tool)}</code></td>"
            f"<td class='{cls}'><strong>{_esc(mark)}</strong></td>"
            f"<td>{_esc(', '.join(r.side_effects))}</td>"
            f"<td><code>{_esc(args_s)}</code></td>"
            f"<td>{_esc(r.reason)}</td>"
            f"<td>{_esc(r.note)}</td>"
            f"</tr>"
        )

    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{_esc(title)} — {overall}</title>
<style>
  :root {{
    --bg: #0b1220;
    --card: #121a2b;
    --text: #e7eefc;
    --muted: #9aa8c7;
    --pass: #3dd68c;
    --fail: #ff6b6b;
    --block: #f0c14b;
    --line: #243047;
    --accent: #6ea8fe;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
    background: radial-gradient(1200px 600px at 10% -10%, #1a2744, var(--bg));
    color: var(--text); line-height: 1.5; padding: 32px 20px 64px;
  }}
  main {{ max-width: 1100px; margin: 0 auto; }}
  .hero {{
    background: linear-gradient(135deg, #152238, #10182a 60%);
    border: 1px solid var(--line); border-radius: 16px; padding: 28px 28px 22px;
    margin-bottom: 24px;
  }}
  h1 {{ margin: 0 0 8px; font-size: 1.6rem; }}
  .badge {{
    display: inline-block; padding: 4px 12px; border-radius: 999px; font-size: 0.85rem;
    font-weight: 700; letter-spacing: 0.04em; margin-left: 8px;
  }}
  .badge.pass {{ background: rgba(61,214,140,0.15); color: var(--pass); border: 1px solid var(--pass); }}
  .badge.fail {{ background: rgba(255,107,107,0.15); color: var(--fail); border: 1px solid var(--fail); }}
  .muted {{ color: var(--muted); }}
  .metrics {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    gap: 12px; margin: 20px 0 8px;
  }}
  .metric {{
    background: var(--card); border: 1px solid var(--line); border-radius: 12px;
    padding: 14px 16px;
  }}
  .metric .n {{ font-size: 1.8rem; font-weight: 700; font-variant-numeric: tabular-nums; }}
  .metric .l {{ color: var(--muted); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.06em; }}
  .metric.ok .n {{ color: var(--pass); }}
  .metric.bad .n {{ color: var(--fail); }}
  .metric.warn .n {{ color: var(--block); }}
  table {{
    width: 100%; border-collapse: collapse; background: var(--card);
    border: 1px solid var(--line); border-radius: 12px; overflow: hidden; font-size: 0.88rem;
  }}
  th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid var(--line); vertical-align: top; }}
  th {{ color: var(--muted); font-weight: 600; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; }}
  tr.pass td.pass, td.pass {{ color: var(--pass); }}
  tr.fail td.fail, td.fail {{ color: var(--fail); }}
  tr.block td.block, td.block {{ color: var(--block); }}
  code {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 0.84em; }}
  footer {{ margin-top: 28px; color: var(--muted); font-size: 0.85rem; }}
  a {{ color: var(--accent); }}
</style>
</head>
<body>
<main>
  <div class="hero">
    <h1>{_esc(title)} <span class="badge {overall_cls}">{overall}</span></h1>
    <p class="muted">session <code>{_esc(summary.session_name)}</code> · mode <code>{_esc(summary.mode)}</code> · { _esc(now) }</p>
    <p>PASS = zero escaped side effects under the demo policy (rogue mutating calls blocked; intended reads allowed).</p>
    <div class="metrics">
      <div class="metric"><div class="n">{summary.total}</div><div class="l">total calls</div></div>
      <div class="metric bad"><div class="n">{summary.blocked}</div><div class="l">blocked</div></div>
      <div class="metric ok"><div class="n">{summary.allowed}</div><div class="l">allowed</div></div>
      <div class="metric warn"><div class="n">{summary.would_write}</div><div class="l">would-write</div></div>
      <div class="metric warn"><div class="n">{summary.would_fetch}</div><div class="l">would-fetch</div></div>
      <div class="metric warn"><div class="n">{summary.would_exec}</div><div class="l">would-exec</div></div>
      <div class="metric {'ok' if summary.escaped_side_effects == 0 else 'bad'}"><div class="n">{summary.escaped_side_effects}</div><div class="l">escaped</div></div>
    </div>
  </div>
  <h2>Per-call rows</h2>
  <table>
    <thead><tr><th>id</th><th>tool</th><th>decision</th><th>side effects</th><th>arguments</th><th>reason</th><th>note</th></tr></thead>
    <tbody>
      {''.join(rows_html)}
    </tbody>
  </table>
  <footer>
    Built with <strong>mcp-stdio-allowlist</strong> —
    <a href="https://github.com/BrickerP/mcp-stdio-allowlist">github.com/BrickerP/mcp-stdio-allowlist</a>
    · Hire: <a href="https://brickerp.github.io/hire/">brickerp.github.io/hire</a>
  </footer>
</main>
</body>
</html>
"""
    out_path.write_text(doc, encoding="utf-8")
    return out_path


def summary_text(summary: GuardSummary) -> str:
    status = "PASS" if summary.passed else "FAIL"
    lines = [
        f"RESULT: {status}",
        f"  mode={summary.mode}  session={summary.session_name}",
        f"  total={summary.total}  blocked={summary.blocked}  allowed={summary.allowed}",
        f"  would-write={summary.would_write}  would-fetch={summary.would_fetch}  would-exec={summary.would_exec}",
        f"  would-token-bypass={summary.would_token_bypass}  would-url-shortener={summary.would_url_shortener}",
        f"  escaped_side_effects={summary.escaped_side_effects}",
    ]
    return "\n".join(lines)
