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


def classify_side_effects(tool: str, arguments: dict[str, Any]) -> set[str]:
    """Return a set of side-effect tags: write, fetch, exec, token_bypass, read."""
    name = tool.lower()
    tags: set[str] = set()

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
    return bool(tags & {"write", "fetch", "exec", "token_bypass", "url_shortener"})
