"""CLI: python -m mcp_stdio_allowlist demo | run | proxy"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .guard import run_session
from .policy import load_policy
from .report import summary_text, write_report, write_spans_jsonl
from .session import load_session


def _repo_root() -> Path:
    # src/mcp_stdio_allowlist/cli.py → repo root
    return Path(__file__).resolve().parents[2]


def cmd_demo(args: argparse.Namespace) -> int:
    root = _repo_root()
    policy_path = Path(args.policy) if args.policy else root / "fixtures" / "policy.json"
    session_path = Path(args.session) if args.session else root / "fixtures" / "rogue_session.json"
    report_path = Path(args.report) if args.report else root / "docs" / "demo-report.html"

    print("mcp-stdio-allowlist demo")
    print("=" * 56)
    print("Use case: dry-run a rogue MCP stdio session that mirrors")
    print("Anthropic-style failure modes (form submit, injection,")
    print("URL shortener, token bypass) against a tight allowlist.")
    print()
    print(f"policy:  {policy_path}")
    print(f"session: {session_path}")
    print(f"mode:    dry-run")
    print()

    policy = load_policy(policy_path)
    session = load_session(session_path)
    summary = run_session(policy, session, mode="dry-run")

    print("Per-call decisions:")
    print("-" * 56)
    for r in summary.rows:
        se = ",".join(r.side_effects)
        print(f"  [{r.decision:12}] {r.tool:28} effects={se}")
        print(f"               {r.reason}")
    print("-" * 56)
    print(summary_text(summary))
    write_report(summary, report_path, title="mcp-stdio-allowlist · rogue session dry-run")
    print(f"  HTML report → {report_path}")
    return 0 if summary.passed else 1


def cmd_demo_jpm(args: argparse.Namespace) -> int:
    """Dry-run our 2026-10-15 X-agent day + JPMorgan-style money probes."""
    root = _repo_root()
    policy_path = Path(args.policy) if args.policy else root / "fixtures" / "jpm_production_policy.json"
    session_path = (
        Path(args.session) if args.session else root / "fixtures" / "jpm_x_agent_day_2026-10-15.json"
    )
    report_path = Path(args.report) if args.report else root / "docs" / "demo-jpm-report.html"
    spans_path = Path(args.spans) if getattr(args, "spans", None) else root / "docs" / "demo-jpm-spans.jsonl"

    print("mcp-stdio-allowlist demo-jpm")
    print("=" * 56)
    print("Use case: replay OUR 2026-10-15 X-agent day as MCP tools/call")
    print("plus JPMorgan-style money/account probes from a third-party")
    print("agent identity. Allow social/network/read; default-deny money.")
    print("Heat: Anthropic Claude Agents OTel traces + outside-agent gate.")
    print()
    print(f"policy:  {policy_path}")
    print(f"session: {session_path}")
    print(f"mode:    dry-run")
    print()

    policy = load_policy(policy_path)
    session = load_session(session_path)
    summary = run_session(policy, session, mode="dry-run")

    print("Per-call decisions:")
    print("-" * 56)
    for r in summary.rows:
        se = ",".join(r.side_effects)
        print(f"  [{r.decision:12}] {r.tool:28} effects={se}")
        print(f"               {r.reason}")
    print("-" * 56)
    print(summary_text(summary, jpm=True))
    write_report(
        summary,
        report_path,
        title="mcp-stdio-allowlist · JPM money gate · 2026-10-15 X-agent day",
    )
    write_spans_jsonl(summary, spans_path)
    print(f"  HTML report → {report_path}")
    print(f"  OTel-ish spans → {spans_path}")
    return 0 if summary.passed else 1


def cmd_run(args: argparse.Namespace) -> int:
    policy = load_policy(args.policy)
    session = load_session(args.session)
    mode = args.mode
    summary = run_session(policy, session, mode=mode)
    print(summary_text(summary))
    if args.report:
        path = write_report(summary, Path(args.report))
        print(f"  HTML report → {path}")
    if args.json:
        payload = {
            "passed": summary.passed,
            "mode": summary.mode,
            "session": summary.session_name,
            "total": summary.total,
            "blocked": summary.blocked,
            "allowed": summary.allowed,
            "would_write": summary.would_write,
            "would_fetch": summary.would_fetch,
            "would_exec": summary.would_exec,
            "escaped_side_effects": summary.escaped_side_effects,
            "rows": [
                {
                    "id": r.id,
                    "tool": r.tool,
                    "decision": r.decision,
                    "side_effects": r.side_effects,
                    "reason": r.reason,
                    "escaped": r.escaped,
                }
                for r in summary.rows
            ],
        }
        print(json.dumps(payload, indent=2))
    return 0 if summary.passed else 1


def cmd_proxy(args: argparse.Namespace) -> int:
    """Optional thin stdio proxy: filter JSON-RPC tools/call on stdin→child stdout."""
    import subprocess
    import threading

    policy = load_policy(args.policy)
    mode = args.mode
    cmd = list(getattr(args, "child", []) or [])
    if cmd and cmd[0] == "--":
        cmd = cmd[1:]
    if not cmd:
        print("proxy requires -- cmd ...", file=sys.stderr)
        return 2

    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=sys.stderr,
        text=True,
        bufsize=1,
    )
    assert proc.stdin and proc.stdout

    blocked = 0
    allowed = 0

    def pump_out() -> None:
        assert proc.stdout
        for line in proc.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()

    t = threading.Thread(target=pump_out, daemon=True)
    t.start()

    from .policy import evaluate_call
    from .side_effects import classify_side_effects, is_mutating

    try:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                proc.stdin.write(line + "\n")
                proc.stdin.flush()
                continue

            method = msg.get("method")
            if method in ("tools/call", "tools/call/request"):
                params = msg.get("params") or {}
                tool = str(params.get("name") or params.get("tool") or "")
                arguments = dict(params.get("arguments") or params.get("args") or {})
                ok, reason = evaluate_call(policy, tool, arguments)
                tags = classify_side_effects(tool, arguments)
                if mode == "dry-run":
                    # never forward mutating / disallowed
                    if not ok or is_mutating(tags):
                        blocked += 1
                        err = {
                            "jsonrpc": "2.0",
                            "id": msg.get("id"),
                            "error": {
                                "code": -32001,
                                "message": f"mcp-stdio-allowlist dry-run blocked: {reason}",
                                "data": {"tool": tool, "side_effects": sorted(tags)},
                            },
                        }
                        sys.stdout.write(json.dumps(err) + "\n")
                        sys.stdout.flush()
                        continue
                else:
                    if not ok:
                        blocked += 1
                        err = {
                            "jsonrpc": "2.0",
                            "id": msg.get("id"),
                            "error": {
                                "code": -32001,
                                "message": f"mcp-stdio-allowlist blocked: {reason}",
                                "data": {"tool": tool, "side_effects": sorted(tags)},
                            },
                        }
                        sys.stdout.write(json.dumps(err) + "\n")
                        sys.stdout.flush()
                        continue
                allowed += 1

            proc.stdin.write(line + "\n")
            proc.stdin.flush()
    except BrokenPipeError:
        pass
    finally:
        try:
            proc.stdin.close()
        except Exception:
            pass
        proc.wait(timeout=5)
        t.join(timeout=2)

    print(f"# proxy summary blocked={blocked} allowed={allowed}", file=sys.stderr)
    return 0


def _dispatch_demo(args: argparse.Namespace) -> int:
    if getattr(args, "scenario", "classic") == "jpm":
        return cmd_demo_jpm(args)
    return cmd_demo(args)


def build_parser() -> argparse.ArgumentParser:

    p = argparse.ArgumentParser(
        prog="mcp_stdio_allowlist",
        description=(
            "Proxy/guard for MCP stdio tool calls — allowlist + dry-run + "
            "side-effect summary in one command."
        ),
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("demo", help="Dry-run bundled rogue MCP session (our usage)")
    d.add_argument("--policy", default=None)
    d.add_argument("--session", default=None)
    d.add_argument("--report", default=None)
    d.add_argument(
        "--scenario",
        choices=["classic", "jpm"],
        default="classic",
        help="classic=rogue Anthropic mirror; jpm=2026-10-15 X-agent + money gate",
    )
    d.set_defaults(func=_dispatch_demo)

    dj = sub.add_parser(
        "demo-jpm",
        help="Dry-run our 2026-10-15 X-agent day + JPMorgan-style money probes",
    )
    dj.add_argument("--policy", default=None)
    dj.add_argument("--session", default=None)
    dj.add_argument("--report", default=None)
    dj.add_argument("--spans", default=None)
    dj.set_defaults(func=cmd_demo_jpm)

    r = sub.add_parser("run", help="Run allowlist against a recorded session")
    r.add_argument("--policy", required=True)
    r.add_argument("--session", required=True)
    r.add_argument("--mode", choices=["enforce", "dry-run"], default="dry-run")
    r.add_argument("--report", default=None)
    r.add_argument("--json", action="store_true")
    r.set_defaults(func=cmd_run)

    px = sub.add_parser("proxy", help="Optional: filter JSON-RPC tools/call over stdio")
    px.add_argument("--policy", required=True)
    px.add_argument("--mode", choices=["enforce", "dry-run"], default="enforce")
    px.add_argument("child", nargs=argparse.REMAINDER, help="Command after -- to wrap")
    px.set_defaults(func=cmd_proxy)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
