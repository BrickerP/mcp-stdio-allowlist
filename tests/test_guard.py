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



class PathAllowlistSecurityTests(unittest.TestCase):
    """Regression: prefix boundary + traversal must not bypass path_prefixes."""

    def setUp(self) -> None:
        self.policy = load_policy(POLICY)

    def test_docs_readme_still_allowed(self) -> None:
        ok, reason = evaluate_call(self.policy, "filesystem.read", {"path": "docs/README.md"})
        self.assertTrue(ok, reason)
        ok2, _ = evaluate_call(self.policy, "filesystem.read", {"path": "./docs/README.md"})
        self.assertTrue(ok2)

    def test_deny_traversal_dotdot(self) -> None:
        for path in (
            "docs/../../etc/passwd",
            "./docs/../.env",
            "docs/../src/mcp_stdio_allowlist/cli.py",
            "docs/foo/../../../etc/passwd",
        ):
            ok, reason = evaluate_call(self.policy, "filesystem.read", {"path": path})
            self.assertFalse(ok, f"should deny {path!r}: {reason}")

    def test_deny_percent_encoded_traversal(self) -> None:
        ok, _ = evaluate_call(
            self.policy, "filesystem.read", {"path": "docs/%2e%2e/%2e%2e/etc/passwd"}
        )
        self.assertFalse(ok)

    def test_deny_prefix_boundary_sibling(self) -> None:
        # Bare prefix "docs" must not match "docs_secret" (startswith without boundary).
        from mcp_stdio_allowlist.policy import Policy, ToolRule, evaluate_call as ev

        loose = Policy(
            version=1,
            description="boundary",
            tools=[ToolRule(name="filesystem.read", path_prefixes=["docs"])],
            default_deny=True,
        )
        ok_ok, _ = ev(loose, "filesystem.read", {"path": "docs/README.md"})
        ok_exact, _ = ev(loose, "filesystem.read", {"path": "docs"})
        ok_bad, reason = ev(loose, "filesystem.read", {"path": "docs_secret/x"})
        self.assertTrue(ok_ok)
        self.assertTrue(ok_exact)
        self.assertFalse(ok_bad, reason)

    def test_deny_nul_and_escape_above_root(self) -> None:
        from mcp_stdio_allowlist.policy import _path_allowed

        self.assertFalse(_path_allowed("docs/x\0/y", ["docs/**"]))
        self.assertFalse(_path_allowed("../etc/passwd", ["docs/**"]))
        self.assertFalse(_path_allowed("/etc/passwd", ["docs/**"]))

if __name__ == "__main__":
    unittest.main()


JPM_POLICY = ROOT / "fixtures" / "jpm_production_policy.json"
JPM_SESSION = ROOT / "fixtures" / "jpm_x_agent_day_2026-10-15.json"


class JpmMoneyGateTests(unittest.TestCase):
    """2026-10-15 production social-agent policy: allow social, block money."""

    def setUp(self) -> None:
        self.policy = load_policy(JPM_POLICY)
        self.session = load_session(JPM_SESSION)

    def test_allow_social_tools(self) -> None:
        for tool, args in (
            ("x.reply", {"text": "hi", "in_reply_to": "1", "_meta": {"agent_identity": "trashConsumer_owned"}}),
            ("x.like", {"post_id": "1", "_meta": {"agent_identity": "trashConsumer_owned"}}),
            ("x.post", {"text": "ship", "_meta": {"agent_identity": "trashConsumer_owned"}}),
            ("x.lead_scan", {"slot": "18:10", "_meta": {"agent_identity": "trashConsumer_owned"}}),
            ("filesystem.read", {"path": "docs/demo-report.html", "_meta": {"agent_identity": "trashConsumer_owned"}}),
            ("http.get", {"url": "https://api.x.com/2/users/me", "method": "GET", "_meta": {"agent_identity": "trashConsumer_owned"}}),
        ):
            ok, reason = evaluate_call(self.policy, tool, args)
            self.assertTrue(ok, f"{tool}: {reason}")

    def test_block_money_probes(self) -> None:
        for tool, args in (
            ("transfer_funds", {"from_account": "a", "to_account": "b", "amount_usd": 1}),
            ("open_customer_account", {"customer_id": "c", "product": "brokerage"}),
            ("authorize_payment", {"merchant": "m", "amount_usd": 1}),
            ("read_customer_ssn", {"customer_id": "c"}),
            ("wire_transfer", {"iban": "XX", "amount_usd": 1}),
        ):
            args = {**args, "_meta": {"agent_identity": "third_party_outside"}}
            ok, reason = evaluate_call(self.policy, tool, args)
            self.assertFalse(ok, f"{tool} should block")
            self.assertTrue(
                "not in allowlist" in reason or "default-denied" in reason,
                reason,
            )

    def test_deny_third_party_identity_even_on_social(self) -> None:
        ok, reason = evaluate_call(
            self.policy,
            "x.reply",
            {"text": "hi", "in_reply_to": "1", "_meta": {"agent_identity": "third_party_outside"}},
        )
        self.assertFalse(ok)
        self.assertIn("default-denied", reason)

    def test_money_side_effect_tags(self) -> None:
        self.assertIn("money", classify_side_effects("transfer_funds", {"amount_usd": 1}))
        self.assertIn("account", classify_side_effects("open_customer_account", {"customer_id": "c"}))
        self.assertIn("pii", classify_side_effects("read_customer_ssn", {"customer_id": "c"}))
        self.assertIn("network", classify_side_effects("x.reply", {"text": "x"}))

    def test_jpm_session_dry_run_pass(self) -> None:
        summary = run_session(self.policy, self.session, mode="dry-run")
        self.assertEqual(summary.total, 19)
        self.assertEqual(summary.blocked, 5)
        self.assertEqual(summary.allowed, 14)
        self.assertEqual(summary.money_probes_blocked, 5)
        self.assertGreaterEqual(summary.social_allowed, 10)
        self.assertEqual(summary.escaped_side_effects, 0)
        self.assertTrue(summary.passed)
        money_tools = {
            "transfer_funds",
            "open_customer_account",
            "authorize_payment",
            "read_customer_ssn",
            "wire_transfer",
        }
        for r in summary.rows:
            if r.tool in money_tools:
                self.assertEqual(r.decision, "WOULD_BLOCK", r.tool)
            else:
                self.assertEqual(r.decision, "WOULD_ALLOW", r.tool)
