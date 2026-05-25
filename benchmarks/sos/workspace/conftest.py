"""Pytest configuration for the workspace test suite."""

import sys
from pathlib import Path

# Ensure the workspace dir is on sys.path so tests can use flat imports
# (``from engine.X import …``) regardless of how pytest was invoked.
# ``python -m pytest`` adds cwd automatically; the bare ``pytest`` binary
# does not, and ``--import-mode=importlib`` disables pytest's own rootdir
# insertion. This conftest covers both.
_WORKSPACE = Path(__file__).resolve().parent
if str(_WORKSPACE) not in sys.path:
    sys.path.insert(0, str(_WORKSPACE))


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "integration: mark test as integration test")
