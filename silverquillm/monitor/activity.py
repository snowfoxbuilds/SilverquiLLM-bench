"""A candidate's stdout event stream rendered for reading (RUN-MONITORING.md, Activity tab).

Claude Code writes ``stream-json`` and Codex writes ``exec --json``; each line becomes zero or
more items a view can colour by kind. A line that is not one of those events is shown raw.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

MAX_TEXT = 600
MAX_LINES = 8
MAX_LINE_LENGTH = 1024 * 1024
# A line cut at the display limit is no longer JSON; its leading type still names it.
EVENT_TYPE = re.compile(r'^\{\s*"type"\s*:\s*"([a-z_.]{1,40})"')
CUT_EVENTS = {
    "user": "result",
    "assistant": "message",
    "item.completed": "result",
    "item.started": "tool",
}


@dataclass(frozen=True)
class ActivityItem:
    kind: str
    """``message``, ``thinking``, ``tool``, ``result``, ``error``, ``task``, ``limit``,
    ``system``, ``done`` or ``raw``."""
    text: str
    failed: bool = False


def shorten(text: str, *, lines: int = MAX_LINES, chars: int = MAX_TEXT) -> str:
    kept = text.strip("\n").splitlines()
    cut = len(kept) > lines
    body = "\n".join(kept[:lines])
    if len(body) > chars:
        body, cut = body[:chars].rstrip(), True
    return body + (" …" if cut else "")


def _text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _tool_input(name: str, payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    for key in ("command", "file_path", "path", "pattern", "url", "query", "description"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    try:
        return json.dumps(payload, sort_keys=True)
    except (TypeError, ValueError):
        return ""


def _tool_result(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(_text(block.get("text")) for block in content if isinstance(block, dict))
    return ""


def _percent(window: Any) -> str | None:
    if not isinstance(window, dict):
        return None
    value = window.get("utilization")
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return f"{100 * value:.0f}%"


def _claude(event: dict) -> list[ActivityItem] | None:
    kind = event.get("type")
    if kind == "system":
        subtype = event.get("subtype")
        if subtype == "init":
            model = _text(event.get("model")) or "?"
            tools = event.get("tools")
            count = len(tools) if isinstance(tools, list) else 0
            return [ActivityItem("system", f"session started · {model} · {count} tools")]
        if subtype == "task_started":
            return [ActivityItem("task", f"started: {_text(event.get('description'))}")]
        if subtype == "task_notification":
            status = _text(event.get("status")) or "done"
            return [ActivityItem("task", f"{status}: {_text(event.get('summary'))}")]
        if subtype == "thinking_tokens":
            return []
        return [ActivityItem("system", _text(subtype) or "system")]
    if kind in ("assistant", "user"):
        message = event.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if isinstance(content, str):
            return [ActivityItem("message", shorten(content))] if kind == "assistant" else []
        if not isinstance(content, list):
            return []
        items = []
        for block in content:
            if not isinstance(block, dict):
                continue
            block_type = block.get("type")
            if block_type == "text" and _text(block.get("text")).strip():
                items.append(ActivityItem("message", shorten(block["text"])))
            elif block_type == "thinking" and _text(block.get("thinking")).strip():
                items.append(ActivityItem("thinking", shorten(block["thinking"], lines=3)))
            elif block_type == "tool_use":
                name = _text(block.get("name")) or "tool"
                detail = shorten(_tool_input(name, block.get("input")), lines=3, chars=300)
                items.append(ActivityItem("tool", f"{name} {detail}".rstrip()))
            elif block_type == "tool_result":
                failed = block.get("is_error") is True
                body = shorten(_tool_result(block.get("content")), lines=4, chars=400)
                items.append(ActivityItem("result", body or "(no output)", failed))
        return items
    if kind == "rate_limit_event":
        info = event.get("rate_limit_info")
        windows = info.get("unifiedWindows") if isinstance(info, dict) else None
        windows = windows if isinstance(windows, dict) else {}
        parts = [
            f"{label} {value}"
            for label, key in (("7-day", "seven_day"), ("5-hour", "five_hour"))
            if (value := _percent(windows.get(key)))
        ]
        return [ActivityItem("limit", "usage " + " · ".join(parts))] if parts else []
    if kind == "result":
        parts = [_text(event.get("subtype")) or "finished"]
        turns = event.get("num_turns")
        if isinstance(turns, int) and not isinstance(turns, bool):
            parts.append(f"{turns} turns")
        cost = event.get("total_cost_usd")
        if isinstance(cost, int | float) and not isinstance(cost, bool):
            parts.append(f"${cost:,.2f} reported")
        return [ActivityItem("done", " · ".join(parts), event.get("is_error") is True)]
    return None


def _codex_item(phase: str, item: dict) -> list[ActivityItem]:
    item_type = item.get("type")
    if item_type == "agent_message":
        text = _text(item.get("text"))
        return [ActivityItem("message", shorten(text))] if phase == "completed" and text else []
    if item_type == "reasoning":
        text = _text(item.get("text"))
        return [ActivityItem("thinking", shorten(text, lines=3))] if text.strip() else []
    if item_type == "command_execution":
        if phase == "started":
            return [ActivityItem("tool", "$ " + shorten(_text(item.get("command")), lines=3))]
        if phase != "completed":
            return []
        code = item.get("exit_code")
        failed = isinstance(code, int) and code != 0
        output = shorten(_text(item.get("aggregated_output")), lines=4, chars=400)
        head = f"exit {code}" if isinstance(code, int) else "done"
        return [ActivityItem("result", f"{head}\n{output}".rstrip(), failed)]
    if item_type == "file_change" and phase == "completed":
        changes = item.get("changes")
        paths = (
            [
                f"{_text(change.get('kind'))} {_text(change.get('path'))}".strip()
                for change in changes
                if isinstance(change, dict)
            ]
            if isinstance(changes, list)
            else []
        )
        return [ActivityItem("tool", "edit " + shorten(", ".join(paths), lines=2, chars=300))]
    if item_type == "todo_list" and phase in ("started", "updated", "completed"):
        entries = item.get("items")
        lines = (
            [
                ("☑ " if entry.get("completed") else "☐ ") + _text(entry.get("text"))
                for entry in entries
                if isinstance(entry, dict)
            ]
            if isinstance(entries, list)
            else []
        )
        return [ActivityItem("task", shorten("\n".join(lines)))] if lines else []
    if item_type == "web_search" and phase == "completed":
        return [ActivityItem("tool", "search " + _text(item.get("query")))]
    if item_type == "mcp_tool_call" and phase == "started":
        return [ActivityItem("tool", f"{_text(item.get('server'))}.{_text(item.get('tool'))}")]
    if item_type == "error":
        return [ActivityItem("error", shorten(_text(item.get("message"))), True)]
    return []


def _codex(event: dict) -> list[ActivityItem] | None:
    kind = event.get("type")
    if not isinstance(kind, str):
        return None
    if kind == "thread.started":
        return [ActivityItem("system", "thread started")]
    if kind == "turn.started":
        return [ActivityItem("system", "turn started")]
    if kind == "turn.completed":
        usage = event.get("usage")
        total = 0
        if isinstance(usage, dict):
            total = sum(
                value
                for key, value in usage.items()
                if key in ("input_tokens", "output_tokens")
                and isinstance(value, int)
                and not isinstance(value, bool)
            )
        return [ActivityItem("done", f"turn completed · {total:,} tokens")]
    if kind in ("turn.failed", "error"):
        error = event.get("error")
        message = error.get("message") if isinstance(error, dict) else event.get("message")
        return [ActivityItem("error", shorten(_text(message) or kind), True)]
    if kind.startswith("item."):
        item = event.get("item")
        if isinstance(item, dict):
            return _codex_item(kind.removeprefix("item."), item)
        return []
    return None


def render_line(line: str) -> list[ActivityItem]:
    """The activity a stdout line describes; a line that is no known event shows raw."""
    stripped = line.strip()
    if not stripped:
        return []
    event = None
    if stripped.startswith("{") and len(stripped) <= MAX_LINE_LENGTH:
        try:
            event = json.loads(stripped)
        except (ValueError, RecursionError):
            event = None
    if isinstance(event, dict):
        items = _claude(event)
        if items is None:
            items = _codex(event)
        if items is not None:
            return items
    elif event is None and (match := EVENT_TYPE.match(stripped)) and match[1] in CUT_EVENTS:
        return [ActivityItem(CUT_EVENTS[match[1]], f"(long {match[1]} event, cut for display)")]
    return [ActivityItem("raw", shorten(stripped, lines=2, chars=300))]
