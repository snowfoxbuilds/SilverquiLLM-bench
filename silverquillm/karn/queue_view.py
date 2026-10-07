"""Read-only rendering of Karn batches for `queue ls`; `top` is the monitor app."""

from __future__ import annotations


def render_rows(rows: list[dict]) -> list[str]:
    if not rows:
        return ["no batches"]
    lines = []
    for row in rows:
        if row["status"] == "unsupported_legacy_batch":
            lines.append(f"{row['batch']} [legacy]: unsupported legacy batch")
        elif row["status"] == "error":
            lines.append(f"{row['batch']} [{row['format']}]: error ({row['error']})")
        else:
            lines.append(
                f"{row['batch']} [{row['format']}]: {row['status']}"
                f" ({row.get('started', 0)}/{row.get('total', 0)})"
            )
    return lines
