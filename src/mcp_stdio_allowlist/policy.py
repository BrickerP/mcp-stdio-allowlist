"""Load and evaluate JSON allowlist policies for MCP tool calls."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


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
    )


def _path_allowed(path: str, prefixes: list[str]) -> bool:
    if not prefixes:
        return True
    # normalize
    p = path.replace("\\", "/")
    for pref in prefixes:
        pref_n = pref.replace("\\", "/")
        # support ./docs/** style: treat trailing /** as prefix match under that dir
        if pref_n.endswith("/**"):
            base = pref_n[:-3]
            if p == base.rstrip("/") or p.startswith(base if base.endswith("/") else base + "/"):
                return True
            # also allow exact file under base when path is relative like docs/README.md
            if base.startswith("./"):
                bare = base[2:]
                if p == bare.rstrip("/") or p.startswith(bare if bare.endswith("/") else bare + "/"):
                    return True
                if p.startswith("./" + bare):
                    return True
        else:
            if p == pref_n or p.startswith(pref_n):
                return True
            if pref_n.startswith("./") and (p == pref_n[2:] or p.startswith(pref_n[2:])):
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


def evaluate_call(policy: Policy, tool_name: str, arguments: dict[str, Any]) -> tuple[bool, str]:
    """Return (allowed, reason)."""
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
