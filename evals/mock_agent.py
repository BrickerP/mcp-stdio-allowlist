"""Scripted agent: replay the sample's prescribed tool call through the guard.

No LLM and no API key. The "injection" is the tool call a compromised agent
would make; the proxy either blocks it (allowlist ON) or lets it through
(allowlist OFF).
"""
from __future__ import annotations

from typing import Any

from mcp_stdio_allowlist.policy import Policy, evaluate_call


def replay_call(
    policy: Policy | None,
    tool: str,
    arguments: dict[str, Any],
    *,
    allowlist_on: bool,
) -> tuple[bool, str]:
    """Return (allowed, reason).

    allowlist_on=False is the unguarded baseline: every prescribed call is allowed.
    """
    if not allowlist_on or policy is None:
        return True, "allowlist off (baseline: call not inspected)"
    return evaluate_call(policy, tool, arguments)
