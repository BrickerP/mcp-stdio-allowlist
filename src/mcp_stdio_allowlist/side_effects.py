"""Classify potential side effects of MCP tool calls."""
from __future__ import annotations

from typing import Any


# tools that imply network / write / exec side effects
WRITE_MARKERS = (
    "write",
    "create",
    "delete",
    "unlink",
    "move",
    "rename",
    "append",
    "put",
    "patch",
    "upload",
    "mkdir",
    "rmdir",
    "truncate",
)
FETCH_MARKERS = (
    "http",
    "fetch",
    "request",
    "download",
    "browse",
    "url",
    "web",
    "curl",
)
EXEC_MARKERS = (
    "shell",
    "exec",
    "run",
    "subprocess",
    "command",
    "bash",
    "terminal",
    "spawn",
)
TOKEN_BYPASS_MARKERS = (
    "bypass",
    "token_gate",
    "fee_gate",
    "skip_auth",
    "impersonate",
)
# JPMorgan-style money / account / PII side effects (default-deny in production)
MONEY_MARKERS = (
    "transfer_funds",
    "wire_transfer",
    "authorize_payment",
    "payment",
    "funds",
    "wire",
    " ACH",
    "ach_",
    "settle",
    "disburse",
)
ACCOUNT_MARKERS = (
    "open_customer_account",
    "customer_account",
    "open_account",
    "close_account",
    "account_create",
)
PII_MARKERS = (
    "read_customer_ssn",
    "customer_ssn",
    "ssn",
    "tax_id",
    "passport_number",
)
# Owned social-agent tools: intentional network side effects under an allowlist
SOCIAL_NETWORK_PREFIXES = (
    "x.",
    "twitter.",
    "social.",
)


def classify_side_effects(tool: str, arguments: dict[str, Any]) -> set[str]:
    """Return a set of side-effect tags: write, fetch, exec, token_bypass, read, network, money, account, pii."""
    name = tool.lower()
    tags: set[str] = set()

    if name.startswith(SOCIAL_NETWORK_PREFIXES) or any(name.startswith(p) for p in SOCIAL_NETWORK_PREFIXES):
        tags.add("network")
        # social tools are intentional egress under policy; do not also tag as write/fetch
        # unless they also match classic mutating markers below via odd naming
        return tags

    for m in MONEY_MARKERS:
        if m.strip().lower() in name:
            tags.add("money")
            break
    for m in ACCOUNT_MARKERS:
        if m.lower() in name:
            tags.add("account")
            break
    for m in PII_MARKERS:
        if m.lower() in name:
            tags.add("pii")
            break
    # argument hints for money/account
    arg_blob = " ".join(str(v).lower() for v in arguments.values() if not isinstance(v, dict))
    arg_keys = " ".join(str(k).lower() for k in arguments.keys())
    if any(k in arg_keys for k in ("amount_usd", "iban", "from_account", "to_account", "instrument")):
        if "money" not in tags and ("transfer" in name or "payment" in name or "wire" in name or "authorize" in name):
            tags.add("money")
    if "customer_id" in arg_keys and ("account" in name or "ssn" in name):
        if "ssn" in name:
            tags.add("pii")
        elif "account" in name:
            tags.add("account")

    for m in WRITE_MARKERS:
        if m in name:
            tags.add("write")
            break
    for m in FETCH_MARKERS:
        if m in name:
            tags.add("fetch")
            break
    for m in EXEC_MARKERS:
        if m in name:
            tags.add("exec")
            break
    for m in TOKEN_BYPASS_MARKERS:
        if m in name:
            tags.add("token_bypass")
            break

    method = str(arguments.get("method") or "").upper()
    if method in ("POST", "PUT", "PATCH", "DELETE"):
        tags.add("write")
        tags.add("fetch")
    if method in ("GET", "HEAD"):
        tags.add("fetch")

    if "url" in arguments or "uri" in arguments:
        tags.add("fetch")
        url = str(arguments.get("url") or arguments.get("uri") or "").lower()
        # URL shorteners / open redirects are classic egress bypass
        for short in ("bit.ly", "t.co", "tinyurl", "goo.gl", "ow.ly", "is.gd"):
            if short in url:
                tags.add("url_shortener")
                break

    if "command" in arguments or "cmd" in arguments or "script" in arguments:
        tags.add("exec")

    if "path" in arguments and "write" not in tags and "exec" not in tags:
        # pure path read-ish tools
        if "read" in name or "get" in name or "list" in name or "stat" in name:
            tags.add("read")

    if not tags:
        tags.add("unknown")
    return tags


def is_mutating(tags: set[str]) -> bool:
    return bool(
        tags
        & {
            "write",
            "fetch",
            "exec",
            "token_bypass",
            "url_shortener",
            "money",
            "account",
            "pii",
        }
    )


def is_dangerous(tags: set[str]) -> bool:
    """Side effects that must never slip through a production money/account gate."""
    return bool(tags & {"money", "account", "pii", "exec", "token_bypass", "url_shortener"})
