"""Load and evaluate JSON allowlist policies for MCP tool calls."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse


@dataclass
class ToolRule:
    name: str
    path_prefixes: list[str] = field(default_factory=list)
    url_hosts: list[str] = field(default_factory=list)
    methods: list[str] = field(default_factory=list)
    # optional: allow only when args match these exact keys present (informational)
    arg_keys: list[str] = field(default_factory=list)


@dataclass
class Policy:
    version: int
    description: str
    tools: list[ToolRule]
    default_deny: bool = True
    denied_agent_identities: list[str] = field(default_factory=list)

    def find(self, tool_name: str) -> ToolRule | None:
        for t in self.tools:
            if t.name == tool_name:
                return t
        return None


def load_policy(path: Path | str) -> Policy:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    tools = []
    for raw in data.get("tools") or []:
        tools.append(
            ToolRule(
                name=raw["name"],
                path_prefixes=list(raw.get("path_prefixes") or []),
                url_hosts=list(raw.get("url_hosts") or []),
                methods=[m.upper() for m in (raw.get("methods") or [])],
                arg_keys=list(raw.get("arg_keys") or []),
            )
        )
    return Policy(
        version=int(data.get("version", 1)),
        description=str(data.get("description") or ""),
        tools=tools,
        default_deny=bool(data.get("default_deny", True)),
        denied_agent_identities=[
            str(x) for x in (data.get("denied_agent_identities") or [])
        ],
    )


def _strip_dot_slash(p: str) -> str:
    """Collapse leading './' segments for comparison. Absolute paths are left unchanged."""
    if p.startswith("/"):
        return p
    while p.startswith("./"):
        p = p[2:]
    return p


def _normalize_path(path: str) -> str | None:
    """Lexical normalize for allowlist checks (no filesystem access).

    Returns None when the path is unsafe for matching:
    - empty after normalize
    - contains NUL
    - ``..`` escapes above the path root (absolute or relative)
    """
    if "\0" in path:
        return None
    # Decode one layer of percent-encoding so %2e%2e / %2f cannot bypass checks.
    raw = unquote(path.replace("\\", "/"))
    if "\0" in raw:
        return None

    is_abs = raw.startswith("/")
    parts: list[str] = []
    for seg in raw.split("/"):
        if seg in ("", "."):
            continue
        if seg == "..":
            if not parts:
                return None
            parts.pop()
            continue
        parts.append(seg)

    if not parts:
        return "/" if is_abs else ""
    norm = "/".join(parts)
    return "/" + norm if is_abs else norm


def _prefix_base(pref: str) -> str:
    """Return the directory/file base of a path_prefixes entry (no trailing /**)."""
    p = pref.replace("\\", "/")
    if p.endswith("/**"):
        p = p[:-3]
    p = p.rstrip("/")
    return _strip_dot_slash(p)


def _path_under_prefix(norm: str, base: str) -> bool:
    """True if *norm* is exactly *base* or a file/dir under it (boundary-safe)."""
    if not base:
        # empty base after strip would allow everything — refuse
        return False
    if norm == base:
        return True
    return norm.startswith(base + "/")


def _path_allowed(path: str, prefixes: list[str]) -> bool:
    if not prefixes:
        return True
    norm = _normalize_path(path)
    if norm is None:
        return False
    # Compare without leading ./ so policy "./docs/**" matches "docs/README.md"
    norm_cmp = _strip_dot_slash(norm)
    # Absolute request vs relative-only prefixes: only match if some prefix is absolute
    for pref in prefixes:
        pref_n = pref.replace("\\", "/")
        base = _prefix_base(pref_n)
        if not base:
            continue
        base_abs = base.startswith("/")
        if norm_cmp.startswith("/") and not base_abs:
            continue
        if not norm_cmp.startswith("/") and base_abs:
            continue
        if _path_under_prefix(norm_cmp, base):
            return True
    return False


def _host_allowed(url: str, hosts: list[str]) -> bool:
    if not hosts:
        return True
    try:
        host = urlparse(url).hostname or ""
    except Exception:
        return False
    host = host.lower()
    for h in hosts:
        h = h.lower().lstrip(".")
        if host == h or host.endswith("." + h):
            return True
    return False


def _agent_identity(arguments: dict[str, Any]) -> str:
    meta = arguments.get("_meta") or arguments.get("meta") or {}
    if isinstance(meta, dict):
        return str(meta.get("agent_identity") or meta.get("identity") or "")
    return str(arguments.get("agent_identity") or "")


def evaluate_call(policy: Policy, tool_name: str, arguments: dict[str, Any]) -> tuple[bool, str]:
    """Return (allowed, reason)."""
    identity = _agent_identity(arguments)
    if identity and policy.denied_agent_identities and identity in policy.denied_agent_identities:
        return False, f"agent_identity '{identity}' is default-denied (outside/untrusted)"

    rule = policy.find(tool_name)
    if rule is None:
        if policy.default_deny:
            return False, f"tool '{tool_name}' not in allowlist"
        return True, "default allow (no rule)"

    # path predicates
    if rule.path_prefixes:
        path = arguments.get("path") or arguments.get("file") or arguments.get("uri") or ""
        if not path:
            return False, f"tool '{tool_name}' requires path matching {rule.path_prefixes}"
        if not _path_allowed(str(path), rule.path_prefixes):
            return False, f"path '{path}' outside allowed prefixes {rule.path_prefixes}"

    # URL / method predicates
    if rule.url_hosts or rule.methods:
        url = arguments.get("url") or arguments.get("uri") or ""
        method = str(arguments.get("method") or "GET").upper()
        if rule.methods and method not in rule.methods:
            return False, f"method {method} not in allowlist {rule.methods}"
        if rule.url_hosts:
            if not url:
                return False, f"tool '{tool_name}' requires url on hosts {rule.url_hosts}"
            if not _host_allowed(str(url), rule.url_hosts):
                return False, f"host of '{url}' not in allowlist {rule.url_hosts}"

    return True, "matched allowlist rule"
