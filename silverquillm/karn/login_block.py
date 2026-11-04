"""Login Blocks: a slot held out of every new run because its login needs signing in again.

The host writes the block when a run's login plugin reports ``relogin needed`` (an expired
or revoked login), so a dead login stops failing run after run. Unlike a Login Cooldown it
has no end time: only a successful re-enrollment of the slot or ``silverquillm login
unblock`` lifts it. A block file that cannot be read still blocks, so a damaged file never
lets a broken login back into the pool.
"""

from __future__ import annotations

import contextlib
import sys
from datetime import UTC, datetime
from pathlib import Path

from .definition import KarnError, canonical, read_regular, strict_json
from .login import write_private

BLOCK_FILE = "blocked.json"
BLOCK_LIMIT = 4096
RELOGIN_NEEDED = "relogin_needed"
# The row key each login plugin's ``on_render_status`` writes its flags under.
STATUS_KEYS = {"karn-claude-login": "claude-login", "karn-codex-login": "codex-login"}


def relogin_needed(plugin_id: str, login_state: list[dict]) -> bool:
    """Whether the plugin's status rows say this login must be signed in again."""
    key = STATUS_KEYS.get(plugin_id)
    for row in login_state if isinstance(login_state, list) else ():
        flags = row.get(key) if isinstance(row, dict) else None
        if isinstance(flags, str) and "relogin needed" in (f.strip() for f in flags.split(",")):
            return True
    return False


def block(directory: Path, *, reason: str, run_id: str | None, now: datetime) -> None:
    stamp = now.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    document = {"format": 1, "reason": reason, "run_id": run_id, "set_at": stamp}
    write_private(Path(directory) / BLOCK_FILE, canonical(document))


def block_if_relogin_needed(
    directory: Path, plugin_id: str, slot: str, login_state: list[dict], run_id: str | None
) -> bool:
    """Block the slot when its plugin reported ``relogin needed``; returns whether it did.

    A block that cannot be written is reported, never raised: it must not cost the run
    its harvest or its record.
    """
    if not relogin_needed(plugin_id, login_state):
        return False
    ref = f"{plugin_id}/{slot}"
    try:
        block(directory, reason=RELOGIN_NEEDED, run_id=run_id, now=datetime.now(UTC))
    except (KarnError, OSError) as error:
        reason = str(error) if isinstance(error, KarnError) else type(error).__name__
        _warn(f"login slot {ref} needs relogin but was not blocked ({reason})")
        return False
    _warn(
        f"blocked login slot {ref}: relogin needed;"
        " re-enroll with `silverquillm login refresh` or lift with `login unblock`"
    )
    return True


def _warn(message: str) -> None:
    # A closed stderr must not cost the run its harvest either.
    with contextlib.suppress(OSError, ValueError):
        print(message, file=sys.stderr, flush=True)


def unblock(directory: Path) -> bool:
    """Lift the slot's block; returns whether one was there."""
    try:
        (Path(directory) / BLOCK_FILE).unlink()
    except FileNotFoundError:
        return False
    return True


def login_block(directory: Path) -> dict | None:
    """The slot's block as ``{reason, run_id, set_at}``, or None when it has none.

    An unreadable block file is a block of unknown reason.
    """
    path = Path(directory) / BLOCK_FILE
    if not path.exists() and not path.is_symlink():
        return None
    try:
        document = strict_json(read_regular(path, limit=BLOCK_LIMIT))
    except KarnError:
        document = None
    if not isinstance(document, dict):
        return {"reason": "unreadable", "run_id": None, "set_at": None}
    run_id, set_at = document.get("run_id"), document.get("set_at")
    return {
        "reason": str(document.get("reason") or "unknown")[:64],
        "run_id": run_id if isinstance(run_id, str) and len(run_id) <= 64 else None,
        "set_at": set_at if isinstance(set_at, str) and len(set_at) <= 32 else None,
    }


def is_blocked(directory: Path) -> bool:
    path = Path(directory) / BLOCK_FILE
    return path.exists() or path.is_symlink()
