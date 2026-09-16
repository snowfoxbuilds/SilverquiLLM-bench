"""Put the SOS workspace dir on ``sys.path`` so flat workspace imports resolve.

The workspace lives at ``benchmarks/sos/workspace/`` in the repo and is mounted
at ``/workspace/`` in the agent container.  Workspace code (``engine``,
``cards``, ``test_utils``) uses flat imports that resolve naturally when the
container's cwd is ``/workspace``.  Harness-side processes (CLI, pytest,
``fetch_data.py``) need the workspace dir on ``sys.path`` to see those names.

Appended rather than prepended to avoid shadowing common module names
(``engine``, ``test_utils``) for unrelated tools running in the same process.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def repository_root() -> Path:
    """The operator-selected benchmark data checkout, or the editable package root."""
    return Path(os.environ.get("SILVERQUILLM_BENCH_ROOT", Path(__file__).resolve().parent.parent)).resolve()


_WORKSPACE = repository_root() / "benchmarks" / "sos" / "workspace"

__all__ = ["ensure_workspace_on_path", "repository_root"]


def ensure_workspace_on_path() -> None:
    path = str(_WORKSPACE)
    if path not in sys.path:
        sys.path.append(path)
