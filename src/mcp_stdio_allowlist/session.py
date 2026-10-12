"""Load recorded MCP-shaped tools/call sessions."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ToolCall:
    id: str
    tool: str
    arguments: dict[str, Any] = field(default_factory=dict)
    note: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class Session:
    name: str
    description: str
    calls: list[ToolCall]


def _from_jsonrpc(msg: dict[str, Any], fallback_id: str) -> ToolCall | None:
    """Parse a JSON-RPC tools/call style message."""
    if msg.get("method") not in ("tools/call", "tools/call/request"):
        # also accept bare {tool, arguments} rows
        if "tool" in msg or "name" in msg:
            tool = msg.get("tool") or msg.get("name")
            args = msg.get("arguments") or msg.get("args") or {}
            return ToolCall(
                id=str(msg.get("id") or fallback_id),
                tool=str(tool),
                arguments=dict(args),
                note=str(msg.get("note") or ""),
                raw=msg,
            )
        return None
    params = msg.get("params") or {}
    tool = params.get("name") or params.get("tool")
    args = params.get("arguments") or params.get("args") or {}
    return ToolCall(
        id=str(msg.get("id") or fallback_id),
        tool=str(tool),
        arguments=dict(args),
        note=str(msg.get("note") or params.get("note") or ""),
        raw=msg,
    )


def load_session(path: Path | str) -> Session:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, list):
        calls_raw = data
        name = Path(path).stem
        description = ""
    else:
        calls_raw = data.get("calls") or data.get("messages") or []
        name = str(data.get("name") or Path(path).stem)
        description = str(data.get("description") or "")

    calls: list[ToolCall] = []
    for i, raw in enumerate(calls_raw):
        tc = _from_jsonrpc(raw, fallback_id=f"call-{i+1}")
        if tc is not None:
            calls.append(tc)
    return Session(name=name, description=description, calls=calls)
