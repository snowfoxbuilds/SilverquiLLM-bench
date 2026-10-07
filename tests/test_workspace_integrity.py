"""Staged Workspaces hold together as a candidate first sees them.

A Workspace is staged through ``stage_benchmark``, the path ``silverquillm run``
stages with, and then checked the way a candidate's container sees it: a
Python that imports only the Workspace, the standard library and installed
tools — no repository root, no ``silverquillm``. Grading runs Audited Tests
beside host support, so nothing else in the repository exercises this view.

The Known-Best Workspace, assembled into a benchmark the way the port
assembles one (``scripts/port_from_known_best.py``) but with no stubs and no
Known Defects, is a candidate that has solved everything: every test it ships
must pass. smoke and fra-hard-v2 are staged as they are; their tests may fail
by design, but every one must collect.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import port_from_known_best as port
from silverquillm.karn.benchmark import load_benchmark, stage_benchmark

REPO = Path(__file__).resolve().parents[1]
SMOKE = REPO / "benchmarks" / "smoke"

# What every Workspace ships for its candidate.
REQUIRED = (
    "AGENTS.md", "PROJECT_MAP.md", "RULEBOOK.txt", "conftest.py", "pytest.ini",
    "test_utils.py", "test_utils.md", "test_interface.py", "test_interface.md",
    "test_test_interface.py", "table.py", "engine", "cards", "engine_tests", "skills",
)

# Runs pytest as the candidate's container would: only the Workspace (the
# working directory), the standard library and installed packages import; a
# module found anywhere else, such as an editable ``silverquillm``, does not.
_ISOLATED = r"""
import importlib.abc, importlib.machinery, os, sys, sysconfig

WORKSPACE = os.path.realpath(os.getcwd())
ALLOWED = {WORKSPACE, *(os.path.realpath(p) for p in sysconfig.get_paths().values())}


def _allowed(origin):
    path = os.path.realpath(origin)
    return any(path == root or path.startswith(root + os.sep) for root in ALLOWED)


class _OnlyTheWorkspace(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        for finder in sys.meta_path:
            if finder is self or not hasattr(finder, "find_spec"):
                continue
            spec = finder.find_spec(name, path, target)
            if spec is None:
                continue
            locations = [spec.origin] if spec.has_location else []
            locations += list(spec.submodule_search_locations or [])
            if any(not _allowed(location) for location in locations if location):
                raise ModuleNotFoundError(f"No module named {name!r} in the Workspace", name=name)
            return None
        return None


sys.meta_path.insert(0, _OnlyTheWorkspace())
sys.path.insert(0, WORKSPACE)
import pytest

sys.exit(pytest.main(sys.argv[1:]))
"""


def _isolated(workspace: Path, *args: str, timeout: int = 900) -> subprocess.CompletedProcess:
    """Run pytest in *workspace* with ``-I`` (no PYTHONPATH, no user site, no
    working directory on the path) and the Workspace-only import guard."""
    env = {"PATH": os.environ.get("PATH", os.defpath), "HOME": str(workspace), "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run(
        [sys.executable, "-I", "-c", _ISOLATED, "-q", "-p", "no:cacheprovider", "-p", "no:xdist", *args],
        cwd=workspace, env=env, capture_output=True, text=True, timeout=timeout, check=False,
    )


def _known_best_benchmark(bench_root: Path) -> None:
    """``bench_root/benchmarks/known-best``: the Known-Best Workspace copied
    by the port's own steps, its Audited Engine Tests seeding the Engine
    Reference Tests, and smoke's agent documents, with smoke's targets left
    implemented and no Known Defects applied."""
    root = bench_root / "benchmarks" / "known-best"
    workspace = root / "workspace"
    workspace.mkdir(parents=True)
    config = json.loads((SMOKE / "config.json").read_text())
    (root / "config.json").write_text(json.dumps({**config, "id": "known-best"}))
    port._copy_known_best_workspace(port.KNOWN_BEST, workspace)
    port._replace(port.KNOWN_BEST / "data/tests/audited/engine", workspace / "engine_tests")
    ported = {item.split("/", 1)[0] for item in port.WORKSPACE_ITEMS} | {"cards", "engine_tests"}
    for entry in (SMOKE / "workspace").iterdir():
        if entry.name not in ported and entry.name != "__pycache__":
            port._replace(entry, workspace / entry.name)


def _staged(bench_root: Path, benchmark_id: str, destination: Path) -> Path:
    stage_benchmark(load_benchmark(bench_root, benchmark_id), destination)
    return destination


def _assert_documented_and_current(workspace: Path) -> None:
    missing = [name for name in REQUIRED if not (workspace / name).exists()]
    assert not missing, f"the Workspace lacks {missing}"
    # Every top-level entry the project map lists is there.
    block = (workspace / "PROJECT_MAP.md").read_text().split("```")[1]
    entries = re.finditer(r"^(\S+)\s+—", block, re.MULTILINE)
    listed = {match.group(1).rstrip("/") for match in entries}
    assert {"AGENTS.md", "engine", "cards", "table.py"} <= listed, f"PROJECT_MAP.md lists {sorted(listed)}"
    absent = sorted(name for name in listed if not (workspace / name).exists())
    assert not absent, f"PROJECT_MAP.md lists entries the Workspace lacks: {absent}"
    # A candidate's Workspace is its own root: no document may point into the repository.
    stale = sorted(
        str(path.relative_to(workspace))
        for path in workspace.rglob("*")
        if path.is_file() and path.suffix in {".md", ".py", ".txt", ".ini"}
        and ".git" not in path.parts
        and re.search(r"\bbenchmarks[/.](?:sos|hob|smoke|fra|known)", path.read_text(errors="ignore"))
    )
    assert not stale, f"files naming repository paths a candidate cannot see: {stale}"


def _collection_errors(result: subprocess.CompletedProcess) -> list[str]:
    return [line for line in result.stdout.splitlines() if line.startswith("ERROR ")]


@pytest.fixture(scope="module")
def known_best_workspace(tmp_path_factory) -> Path:
    bench_root = tmp_path_factory.mktemp("bench")
    _known_best_benchmark(bench_root)
    return _staged(bench_root, "known-best", tmp_path_factory.mktemp("staged") / "workspace")


def test_python_and_pytest_run_with_only_the_workspace(known_best_workspace: Path) -> None:
    probe = known_best_workspace / "test_probe_imports.py"
    probe.write_text(
        "import importlib, pytest\n\n"
        "def test_the_workspace_imports_alone():\n"
        "    for name in ('engine', 'cards', 'test_utils', 'test_interface', 'table'):\n"
        "        importlib.import_module(name)\n"
        "    with pytest.raises(ModuleNotFoundError):\n"
        "        importlib.import_module('silverquillm')\n"
    )
    try:
        result = _isolated(known_best_workspace, str(probe))
    finally:
        probe.unlink()
    assert result.returncode == 0, result.stdout[-4000:] + result.stderr[-2000:]


def test_known_best_workspace_is_documented_and_current(known_best_workspace: Path) -> None:
    _assert_documented_and_current(known_best_workspace)


def test_every_test_in_the_known_best_workspace_passes(known_best_workspace: Path) -> None:
    result = _isolated(known_best_workspace, "-rfE")
    assert not _collection_errors(result), "\n".join(_collection_errors(result))
    assert result.returncode == 0, result.stdout[-6000:] + result.stderr[-2000:]
    assert re.search(r"\b\d+ passed\b", result.stdout)


@pytest.fixture(scope="module", params=["smoke", "fra-hard-v2"])
def benchmark_workspace(request, tmp_path_factory) -> Path:
    return _staged(REPO, request.param, tmp_path_factory.mktemp(request.param) / "workspace")


def test_every_test_in_a_ported_benchmark_workspace_collects(benchmark_workspace: Path) -> None:
    result = _isolated(benchmark_workspace, "--collect-only")
    assert result.returncode == 0 and not _collection_errors(result), (
        result.stdout[-6000:] + result.stderr[-2000:]
    )


def test_a_ported_benchmark_workspace_is_documented_and_current(benchmark_workspace: Path) -> None:
    _assert_documented_and_current(benchmark_workspace)
    agents = (benchmark_workspace / "AGENTS.md").read_text()
    if "instructions.md" in agents:
        assert (benchmark_workspace / "instructions.md").is_file(), "AGENTS.md names a missing instructions.md"
