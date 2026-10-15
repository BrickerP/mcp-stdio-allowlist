"""Enforce / dry-run guard over a session of MCP tool calls."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from .policy import Policy, evaluate_call
from .session import Session, ToolCall
from .side_effects import classify_side_effects, is_dangerous, is_mutating

Mode = Literal["enforce", "dry-run"]


@dataclass
class CallResult:
    id: str
    tool: str
    arguments: dict[str, Any]
    allowed: bool
    would_allow: bool
    reason: str
    side_effects: list[str]
    decision: str  # ALLOWED | BLOCKED | WOULD_ALLOW | WOULD_BLOCK
    note: str = ""
    escaped: bool = False  # True if a mutating call slipped through


@dataclass
class GuardSummary:
    mode: Mode
    session_name: str
    total: int = 0
    allowed: int = 0
    blocked: int = 0
    would_allow: int = 0
    would_block: int = 0
    would_write: int = 0
    would_fetch: int = 0
    would_exec: int = 0
    would_token_bypass: int = 0
    would_url_shortener: int = 0
    would_money: int = 0
    would_account: int = 0
    would_pii: int = 0
    social_allowed: int = 0
    money_probes_blocked: int = 0
    escaped_side_effects: int = 0
    rows: list[CallResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """PASS = zero escaped side effects under dry-run/enforce for the demo policy."""
        return self.escaped_side_effects == 0 and self.total > 0


def guard_call(policy: Policy, call: ToolCall, mode: Mode) -> CallResult:
    ok, reason = evaluate_call(policy, call.tool, call.arguments)
    tags = classify_side_effects(call.tool, call.arguments)
    mutating = is_mutating(tags)

    if mode == "dry-run":
        # dry-run: allow nothing with side effects; report what WOULD happen
        if ok and not mutating:
            decision = "WOULD_ALLOW"
            allowed = False  # dry-run never executes
            escaped = False
        elif ok and mutating:
            decision = "WOULD_ALLOW"
            allowed = False
            escaped = False  # dry-run prevented execution
        else:
            decision = "WOULD_BLOCK"
            allowed = False
            escaped = False
        return CallResult(
            id=call.id,
            tool=call.tool,
            arguments=call.arguments,
            allowed=allowed,
            would_allow=ok,
            reason=reason,
            side_effects=sorted(tags),
            decision=decision,
            note=call.note,
            escaped=escaped,
        )

    # enforce
    if ok:
        decision = "ALLOWED"
        escaped = mutating  # if policy wrongly allows a mutating call, count as escaped
        return CallResult(
            id=call.id,
            tool=call.tool,
            arguments=call.arguments,
            allowed=True,
            would_allow=True,
            reason=reason,
            side_effects=sorted(tags),
            decision=decision,
            note=call.note,
            escaped=escaped and not _intentional_allow(tags),
        )
    return CallResult(
        id=call.id,
        tool=call.tool,
        arguments=call.arguments,
        allowed=False,
        would_allow=False,
        reason=reason,
        side_effects=sorted(tags),
        decision="BLOCKED",
        note=call.note,
        escaped=False,
    )


def _read_only_allowed(tags: set[str]) -> bool:
    """filesystem.read / http.get alone are intentional allowlist hits, not escapes."""
    return tags <= {"read", "fetch"} and not is_dangerous(tags)


def _intentional_allow(tags: set[str]) -> bool:
    """Allowlisted social network tools and read/fetch are intentional, not escapes."""
    if "network" in tags and tags <= {"network"}:
        return True
    return _read_only_allowed(tags)


def run_session(policy: Policy, session: Session, mode: Mode = "dry-run") -> GuardSummary:
    summary = GuardSummary(mode=mode, session_name=session.name)
    for call in session.calls:
        row = guard_call(policy, call, mode)
        summary.rows.append(row)
        summary.total += 1
        tags = set(row.side_effects)

        if mode == "dry-run":
            if row.would_allow:
                summary.would_allow += 1
            else:
                summary.would_block += 1
            # count side effects that WOULD have happened if unguarded / if allowed
            if not row.would_allow:
                # blocked by policy — these are the "caught" mutating attempts
                if "write" in tags:
                    summary.would_write += 1
                if "fetch" in tags and ("write" in tags or "url_shortener" in tags or row.tool.lower().startswith("http_post") or "post" in row.tool.lower()):
                    summary.would_fetch += 1
                elif "fetch" in tags and not row.would_allow:
                    summary.would_fetch += 1
                if "exec" in tags:
                    summary.would_exec += 1
                if "token_bypass" in tags:
                    summary.would_token_bypass += 1
                if "url_shortener" in tags:
                    summary.would_url_shortener += 1
                if "money" in tags:
                    summary.would_money += 1
                    summary.money_probes_blocked += 1
                if "account" in tags:
                    summary.would_account += 1
                    if "money" not in tags and "pii" not in tags:
                        summary.money_probes_blocked += 1
                if "pii" in tags:
                    summary.would_pii += 1
                    if "money" not in tags:
                        summary.money_probes_blocked += 1
            if row.would_allow and "network" in tags:
                summary.social_allowed += 1
            elif row.would_allow and _intentional_allow(tags):
                # reads / allowlisted fetch also count toward "allowed social day" narrative via allowed
                pass
            # escaped = dangerous/mutating call that policy would allow (policy hole)
            if row.would_allow and is_mutating(tags) and not _intentional_allow(tags):
                summary.escaped_side_effects += 1
                row.escaped = True
            else:
                row.escaped = False
        else:
            if row.allowed:
                summary.allowed += 1
            else:
                summary.blocked += 1
            if not row.allowed:
                if "write" in tags:
                    summary.would_write += 1
                if "fetch" in tags:
                    summary.would_fetch += 1
                if "exec" in tags:
                    summary.would_exec += 1
                if "token_bypass" in tags:
                    summary.would_token_bypass += 1
                if "url_shortener" in tags:
                    summary.would_url_shortener += 1
                if "money" in tags:
                    summary.would_money += 1
                    summary.money_probes_blocked += 1
                if "account" in tags:
                    summary.would_account += 1
                    if "money" not in tags and "pii" not in tags:
                        summary.money_probes_blocked += 1
                if "pii" in tags:
                    summary.would_pii += 1
                    if "money" not in tags:
                        summary.money_probes_blocked += 1
            if row.allowed and "network" in tags:
                summary.social_allowed += 1
            if row.escaped:
                summary.escaped_side_effects += 1

    # For dry-run demo PASS semantics: blocked (would_block) rogue calls + allowed reads,
    # with zero escaped side effects (mutating calls that policy would wrongly allow).
    if mode == "dry-run":
        # present blocked/allowed in summary for README-style numbers
        summary.blocked = summary.would_block
        summary.allowed = summary.would_allow

    return summary
