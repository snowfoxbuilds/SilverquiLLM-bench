"""Pre-flight validation for benchmark runs.

Validates the environment before any LLM calls to avoid wasting budget on
a misconfigured setup.
"""

from __future__ import annotations

import importlib
import os
import shutil
import stat
import subprocess
import sys
import warnings
from pathlib import Path
from typing import List

from silverquillm.config import BenchmarkConfig, _VALID_MODES

# Repository root (silverquillm/preflight.py → repo root)
_REPO_ROOT = Path(__file__).resolve().parent.parent


class PreflightError(Exception):
    """Raised when a pre-flight check fails."""


def preflight_check(
    config: BenchmarkConfig,
    run_dir: Path,
    *,
    skip_engine_tests: bool = False,
) -> None:
    """Run all pre-flight checks before entering the card loop.

    Parameters
    ----------
    config:
        Validated benchmark configuration.
    run_dir:
        The results directory for this run (must be creatable / writable).
    skip_engine_tests:
        When ``True``, skip the engine test suite check.  Useful for rapid
        iteration during development when the engine is known-good.

    Raises
    ------
    PreflightError
        If any check fails, with a clear message describing the problem.
    """
    errors: List[str] = []

    errors.extend(_check_template_imports())
    errors.extend(_check_test_utils_import())
    errors.extend(_check_workspace(run_dir))
    errors.extend(_check_workspace_dir())
    if not skip_engine_tests:
        errors.extend(_check_engine_tests())
    errors.extend(_check_config(config))
    errors.extend(_check_card_specs_dir(config))

    if errors:
        msg = "Pre-flight checks failed:\n" + "\n".join(f"  - {e}" for e in errors)
        raise PreflightError(msg)


def _check_template_imports() -> List[str]:
    """Verify template.py imports resolve (engine.game_state, engine.card, etc.)."""
    errors: List[str] = []
    modules = ["engine.game_state", "engine.card"]
    for mod_name in modules:
        try:
            importlib.import_module(mod_name)
        except ImportError as exc:
            errors.append(f"Template import failed: cannot import {mod_name!r} ({exc})")
    return errors


def _check_test_utils_import() -> List[str]:
    """Verify test_utils.py exists and the flat import path works.

    Checks that the file exists in the expected location (tests/test_utils.py)
    relative to the repository root, and that ``from test_utils import create_game``
    actually resolves — catching syntax errors or missing symbols early.
    """
    errors: List[str] = []
    # Locate repo root relative to this file (silverquillm/preflight.py → repo root)
    repo_root = Path(__file__).resolve().parent.parent
    test_utils_path = repo_root / "tests" / "test_utils.py"
    if not test_utils_path.exists():
        errors.append(
            f"test_utils.py not found at {test_utils_path}; "
            f"'from test_utils import create_game' will fail in generated templates"
        )
        return errors

    # Actually verify the flat import resolves and create_game is accessible.
    # Use a subprocess so we don't pollute the current process' sys.path/modules.
    # PYTHONPATH must include both repo root (for engine.*) and tests/ (for
    # the flat `test_utils` import path).
    env = os.environ.copy()
    extra = os.pathsep.join([str(repo_root), str(repo_root / "tests")])
    env["PYTHONPATH"] = extra + os.pathsep + env.get("PYTHONPATH", "")
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from test_utils import create_game; assert callable(create_game)",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            errors.append(
                f"'from test_utils import create_game' failed: {stderr}"
            )
    except Exception as exc:
        errors.append(f"Failed to verify test_utils import: {exc}")

    return errors


def _check_workspace(run_dir: Path) -> List[str]:
    """Verify run results directory can be created."""
    errors: List[str] = []
    try:
        run_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        errors.append(f"Cannot create run directory {run_dir}: {exc}")
    return errors


def _check_workspace_dir() -> List[str]:
    """Verify the .workspace/ directory can be created and cleaned.

    AgentSession.setup_workspace() creates `<repo_root>/.workspace/` and
    removes stale contents (including read-only files).  We validate that
    this directory is writable and cleanable before any LLM calls.
    """
    errors: List[str] = []
    workspace = _REPO_ROOT / ".workspace"
    try:
        workspace.mkdir(parents=True, exist_ok=True)
        # Verify we can write a probe file
        probe = workspace / ".preflight_probe"
        probe.write_text("probe")
        probe.unlink()
    except OSError as exc:
        errors.append(
            f"Cannot create/write .workspace/ directory at {workspace}: {exc}"
        )
    return errors


def _check_engine_tests() -> List[str]:
    """Run the engine test suite and verify it passes.

    Executes ``pytest tests/engine/ -x -q`` via subprocess to confirm the
    engine is in a working state before spending LLM budget.
    """
    errors: List[str] = []
    tests_dir = _REPO_ROOT / "tests" / "engine"
    if not tests_dir.is_dir():
        errors.append(f"Engine test directory not found: {tests_dir}")
        return errors

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(tests_dir), "-x", "-q",
             "--no-header", "--tb=line"],
            cwd=str(_REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            # Extract the last few lines for a concise error
            out = (result.stdout + result.stderr).strip().splitlines()
            summary = "\n    ".join(out[-5:]) if len(out) > 5 else "\n    ".join(out)
            errors.append(
                f"Engine test suite failed (exit code {result.returncode}):\n    {summary}"
            )
    except subprocess.TimeoutExpired:
        errors.append("Engine test suite timed out (>120s)")
    except Exception as exc:
        errors.append(f"Failed to run engine test suite: {exc}")

    return errors


def _check_config(config: BenchmarkConfig) -> List[str]:
    """Validate config fields: timeout > 0, adapter exists, mode is valid."""
    errors: List[str] = []

    # timeout_per_card > 0
    if config.agent.timeout_per_card <= 0:
        errors.append(
            f"timeout_per_card must be > 0, got {config.agent.timeout_per_card}"
        )

    # adapter exists in registry
    from silverquillm.adapters.base import _ADAPTER_REGISTRY

    adapter_name = config.agent.adapter
    if adapter_name not in _ADAPTER_REGISTRY:
        available = ", ".join(sorted(_ADAPTER_REGISTRY)) or "(none)"
        errors.append(
            f"Unknown adapter {adapter_name!r}. "
            f"Available adapters: {available}"
        )

    # mode is valid
    if config.mode not in _VALID_MODES:
        errors.append(
            f"Invalid mode {config.mode!r}; must be one of {sorted(_VALID_MODES)}"
        )

    return errors


def _check_card_specs_dir(config: BenchmarkConfig) -> List[str]:
    """Verify card_specs_dir exists and contains at least one card spec."""
    errors: List[str] = []
    specs_dir = config.card_specs_dir
    if not specs_dir:
        # No card_specs_dir configured — will use default in CLI, skip check
        return errors

    path = Path(specs_dir)
    if not path.exists():
        errors.append(f"card_specs_dir does not exist: {specs_dir}")
        return errors

    if not path.is_dir():
        errors.append(f"card_specs_dir is not a directory: {specs_dir}")
        return errors

    # Check for at least one YAML/JSON card spec
    spec_files = list(path.glob("*.yaml")) + list(path.glob("*.yml")) + list(path.glob("*.json"))
    if not spec_files:
        errors.append(f"card_specs_dir contains no card spec files: {specs_dir}")

    return errors
