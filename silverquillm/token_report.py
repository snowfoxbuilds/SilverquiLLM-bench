"""Token usage breakdown from Claude Code stream-json logs.

Parses ``agent_stdout.log`` (one JSON event per line, emitted by
``claude -p --output-format stream-json``) and attributes per-message
``usage`` to the subagent that produced it.

Attribution rule: each ``type:"assistant"`` event has a top-level
``parent_tool_use_id``. If it points at a prior ``Task`` tool_use call,
the message belongs to that call's ``subagent_type``. If it is null, the
message belongs to the top-level agent (labelled ``main``).
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Iterator


def _iter_events(log_path: Path) -> Iterator[dict]:
    with log_path.open() as f:
        for line in f:
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def parse_usage(log_path: Path) -> tuple[dict[tuple[str, str], dict], list[dict]]:
    """Walk ``log_path`` and return (per-(agent,model) totals, result events).

    Each ``claude -p`` session emits one final ``result`` event carrying
    authoritative cost (``modelUsage[*].costUSD`` / ``total_cost_usd``) we can't
    compute per-message. A single run may contain more than one session — e.g. a
    multi-phase entrypoint that invokes ``claude`` once per phase — so we collect
    *every* ``result`` event and let the caller sum cost across them, instead of
    keeping only the last session's.
    """
    task_to_agent: dict[str, str] = {}
    agg: dict[tuple[str, str], dict] = defaultdict(
        lambda: {"messages": 0, "input": 0, "output": 0, "cache_read": 0, "cache_creation": 0}
    )
    result_events: list[dict] = []

    for evt in _iter_events(log_path):
        etype = evt.get("type")

        if etype == "result":
            result_events.append(evt)
            continue

        # Authoritative subagent-start marker. Carries tool_use_id + subagent_type
        # directly, so we don't have to guess which tool name (Agent vs. Task)
        # this Claude Code version uses for subagent dispatch.
        if etype == "system" and evt.get("subtype") == "task_started":
            tid = evt.get("tool_use_id")
            subagent = evt.get("subagent_type")
            if tid and subagent:
                task_to_agent[tid] = subagent
            continue

        if etype != "assistant":
            continue

        msg = evt.get("message", {}) or {}
        model = msg.get("model", "unknown")

        # Fallback: also scan tool_use blocks named Agent/Task in case a
        # particular Claude Code version doesn't emit task_started events.
        for block in msg.get("content", []) or []:
            if block.get("type") == "tool_use" and block.get("name") in ("Agent", "Task"):
                tid = block.get("id")
                subagent = (block.get("input") or {}).get("subagent_type", "unknown")
                if tid:
                    task_to_agent.setdefault(tid, subagent)

        usage = msg.get("usage")
        if not usage:
            continue

        parent_id = evt.get("parent_tool_use_id")
        agent = "main" if parent_id is None else task_to_agent.get(parent_id, "unknown")

        bucket = agg[(agent, model)]
        bucket["messages"] += 1
        bucket["input"] += usage.get("input_tokens", 0) or 0
        bucket["output"] += usage.get("output_tokens", 0) or 0
        bucket["cache_read"] += usage.get("cache_read_input_tokens", 0) or 0
        bucket["cache_creation"] += usage.get("cache_creation_input_tokens", 0) or 0

    return agg, result_events


def format_table(
    agg: dict[tuple[str, str], dict],
    result_events: list[dict] | None = None,
) -> str:
    """Render per-(agent, model) totals as a monospace text table.

    Cost is summed across every ``result`` event (one per ``claude`` session), so
    a multi-phase run reports its full cost, not just the last phase's.
    """
    if not agg:
        return "(no token usage events found in log)"

    cost_by_model: dict[str, float] = {}
    summed_total = 0.0
    any_total = False
    for result in result_events or []:
        for model, mu in (result.get("modelUsage") or {}).items():
            cost_by_model[model] = cost_by_model.get(model, 0.0) + (mu.get("costUSD", 0.0) or 0.0)
        tc = result.get("total_cost_usd")
        if tc is not None:
            summed_total += tc
            any_total = True

    cols = ("Agent", "Model", "Msgs", "Input", "Cache rd", "Cache wr", "Output")
    rows: list[tuple[str, ...]] = []

    for (agent, model), t in sorted(agg.items()):
        rows.append((
            agent,
            model,
            f"{t['messages']:,}",
            f"{t['input']:,}",
            f"{t['cache_read']:,}",
            f"{t['cache_creation']:,}",
            f"{t['output']:,}",
        ))

    total = {k: sum(b[k] for b in agg.values()) for k in ("messages", "input", "output", "cache_read", "cache_creation")}
    total_row = (
        "TOTAL", "",
        f"{total['messages']:,}",
        f"{total['input']:,}",
        f"{total['cache_read']:,}",
        f"{total['cache_creation']:,}",
        f"{total['output']:,}",
    )

    widths = [len(c) for c in cols]
    for r in rows + [total_row]:
        for i, cell in enumerate(r):
            widths[i] = max(widths[i], len(cell))

    def fmt(row: tuple[str, ...]) -> str:
        return "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row))

    divider = "  ".join("-" * w for w in widths)
    lines = [fmt(cols), divider]
    lines.extend(fmt(r) for r in rows)
    lines.append(divider)
    lines.append(fmt(total_row))

    if cost_by_model:
        lines.append("")
        lines.append("Cost (USD) by model — summed across agent sessions:")
        for model in sorted(cost_by_model):
            lines.append(f"  {model:<35s} ${cost_by_model[model]:.4f}")
        total_cost = summed_total if any_total else sum(cost_by_model.values())
        lines.append(f"  {'TOTAL':<35s} ${total_cost:.4f}")

    return "\n".join(lines)


def render(log_path: Path) -> str | None:
    """Parse + format ``log_path``. Returns ``None`` when the log isn't a
    Claude Code stream-json log (e.g. Copilot's plain-text output) so callers
    can skip emission entirely."""
    if not log_path.exists():
        return None
    agg, results = parse_usage(log_path)
    if not agg and not results:
        return None
    return format_table(agg, results)
