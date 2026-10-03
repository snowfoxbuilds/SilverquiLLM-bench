"""The temp footprint a passing session may leave in its basetemp (#140).

CI's basetemp sits on the host's small ``/tmp`` tmpfs. A passed test's
``tmp_path`` is removed at its teardown (``tmp_path_retention_policy`` in
``pyproject.toml``), so a passing session keeps only the directories of
wider-scoped ``tmp_path_factory`` fixtures. A session that keeps more than the
budget fails, naming the largest directories, so a fixture that stops
cleaning up is caught before it fills the tmpfs.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

RETAINED_TEMP_BUDGET_BYTES = 256 * 1024 * 1024

#: The basetemp pytest-xdist gives each worker inside the controller's.
_XDIST_WORKER = re.compile(r"popen-gw\d+")


def tree_bytes(path: Path) -> int:
    """Return the size of the regular files under ``path``, not following symlinks."""
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.lstat(os.path.join(root, name)).st_size
            except OSError:
                pass
    return total


def retained_dirs(basetemp: Path) -> dict[str, Path]:
    """Name each directory a session kept, looking inside pytest-xdist workers' basetemps."""
    found: dict[str, Path] = {}
    for child in _subdirs(basetemp):
        if _XDIST_WORKER.fullmatch(child.name):
            found.update({f"{child.name}/{grandchild.name}": grandchild for grandchild in _subdirs(child)})
        else:
            found[child.name] = child
    return found


def _subdirs(path: Path) -> list[Path]:
    # pytest's ``<name>current`` entries are symlinks to a numbered directory already counted.
    return [child for child in path.iterdir() if child.is_dir() and not child.is_symlink()]


def over_budget(basetemp: Path, budget: int | None = None) -> list[str]:
    """Describe what ``basetemp`` keeps when it exceeds ``budget``; empty when within it."""
    if budget is None:
        budget = RETAINED_TEMP_BUDGET_BYTES
    sizes = {name: tree_bytes(path) for name, path in retained_dirs(basetemp).items()}
    retained = sum(sizes.values())
    if retained <= budget:
        return []
    largest = sorted(sizes.items(), key=lambda item: item[1], reverse=True)[:10]
    summary = (
        f"a passing session left {retained / 2**20:.0f} MiB in {basetemp}, "
        f"over the {budget / 2**20:.0f} MiB budget; largest directories:"
    )
    return [
        summary,
        *(f"  {size / 2**20:8.1f} MiB  {name}" for name, size in largest),
    ]
