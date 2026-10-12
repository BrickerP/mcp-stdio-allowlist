"""Unit tests for mcp-stdio-allowlist."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from mcp_stdio_allowlist.guard import run_session
from mcp_stdio_allowlist.policy import evaluate_call, load_policy
from mcp_stdio_allowlist.session import load_session
from mcp_stdio_allowlist.side_effects import classify_side_effects
from mcp_stdio_allowlist.report import write_report, summary_text


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "fixtures" / "policy.json"
SESSION = ROOT / "fixtures" / "rogue_session.json"


class PolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = load_policy(POLICY)

    def test_allow_docs_read(self) -> None:
        ok, reason = evaluate_call(self.policy, "filesystem.read", {"path": "docs/README.md"})
        self.assertTrue(ok, reason)

    def test_deny_etc_passwd(self) -> None:
        ok, _ = evaluate_call(self.policy, "filesystem.read", {"path": "/etc/passwd"})
        self.assertFalse(ok)

    def test_allow_github_zen(self) -> None:
        ok, reason = evaluate_call(
            self.policy, "http.get", {"url": "https://api.github.com/zen", "method": "GET"}
        )
        self.assertTrue(ok, reason)

    def test_deny_unknown_tool(self) -> None:
        ok, reason = evaluate_call(self.policy, "shell_exec", {"command": "id"})
        self.assertFalse(ok)
        self.assertIn("not in allowlist", reason)


class SideEffectTests(unittest.TestCase):
    def test_shell_is_exec(self) -> None:
        tags = classify_side_effects("shell_exec", {"command": "rm -rf /"})
        self.assertIn("exec", tags)

    def test_post_is_write_fetch(self) -> None:
        tags = classify_side_effects("http_post", {"url": "https://x.test", "method": "POST"})
        self.assertIn("write", tags)
        self.assertIn("fetch", tags)

    def test_bitly_flagged(self) -> None:
        tags = classify_side_effects("http_get", {"url": "https://bit.ly/abc", "method": "GET"})
        self.assertIn("url_shortener", tags)


class DemoSessionTests(unittest.TestCase):
    def test_dry_run_blocks_four_allows_two(self) -> None:
        policy = load_policy(POLICY)
        session = load_session(SESSION)
        summary = run_session(policy, session, mode="dry-run")
        self.assertEqual(summary.total, 6)
        self.assertEqual(summary.blocked, 4)
        self.assertEqual(summary.allowed, 2)
        self.assertEqual(summary.escaped_side_effects, 0)
        self.assertTrue(summary.passed)
        decisions = {r.id: r.decision for r in summary.rows}
        self.assertEqual(decisions["1"], "WOULD_BLOCK")
        self.assertEqual(decisions["2"], "WOULD_BLOCK")
        self.assertEqual(decisions["3"], "WOULD_BLOCK")
        self.assertEqual(decisions["4"], "WOULD_BLOCK")
        self.assertEqual(decisions["5"], "WOULD_ALLOW")
        self.assertEqual(decisions["6"], "WOULD_ALLOW")

    def test_enforce_same_counts(self) -> None:
        policy = load_policy(POLICY)
        session = load_session(SESSION)
        summary = run_session(policy, session, mode="enforce")
        self.assertEqual(summary.blocked, 4)
        self.assertEqual(summary.allowed, 2)
        self.assertTrue(summary.passed)

    def test_report_writes(self) -> None:
        policy = load_policy(POLICY)
        session = load_session(SESSION)
        summary = run_session(policy, session, mode="dry-run")
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "report.html"
            write_report(summary, out)
            html = out.read_text(encoding="utf-8")
            self.assertIn("PASS", html)
            self.assertIn("blocked", html.lower())
            text = summary_text(summary)
            self.assertIn("RESULT: PASS", text)


if __name__ == "__main__":
    unittest.main()
