"""Root-level conftest so `pytest` (the script) can import top-level packages.

`python -m pytest` adds CWD to sys.path automatically; the `pytest` console
script does not. Combined with `--import-mode=importlib` (set in pyproject),
pytest never inserts the rootdir into sys.path on its own. Without this file,
imports like `from benchmarks.sos.fetch_data import ...` raise
ModuleNotFoundError when invoked as `pytest`.
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = str(Path(__file__).resolve().parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
