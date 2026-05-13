"""Pre-flight validation for benchmark runs.

Validates the environment before any LLM calls to avoid wasting budget on
a misconfigured setup.
"""

from __future__ import annotations

import importlib
import logging
import os
import shutil
import stat
import subprocess
import sys
import uuid
import warnings
from pathlib import Path
from typing import List

from silverquillm.config import BenchmarkConfig, _VALID_MODES

# Repository root (silverquillm/preflight.py → repo root)
_REPO_ROOT = Path(__file__).resolve().parent.parent


class PreflightError(Exception):
    """Raised when a pre-flight check fails."""


logger = logging.getLogger(__name__)


def preflight_check(
    config: BenchmarkConfig,
    run_dir: Path,
    *,
    skip_engine_tests: bool = False,
    skip_isolation_check: bool = False,
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
    skip_isolation_check:
        When ``True``, skip the workspace isolation canary check.  Useful
        when no working adapter is available or to avoid making an LLM call
        during preflight.

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
    if not skip_isolation_check:
        errors.extend(_check_workspace_isolation(config))

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
            timeout=300,
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
    spec_files = (
        list(path.glob("*/card_spec.json"))    # subdirectory layout: cards/1/card_spec.json
        + list(path.glob("*/card_spec.yaml"))   # also support YAML variant
        + list(path.glob("*.yaml"))             # flat layout fallback
        + list(path.glob("*.yml"))
        + list(path.glob("*.json"))
)
    # Filter out .gitkeep and similar non-spec files
    spec_files = [f for f in spec_files if f.name != ".gitkeep"]
    if not spec_files:
        errors.append(f"card_specs_dir contains no card spec files: {specs_dir}")

    return errors


def _check_workspace_isolation(config: BenchmarkConfig) -> List[str]:
    """Verify the agent adapter cannot escape the workspace.

    Creates a canary file at ``_REPO_ROOT / ".canary_preflight"`` with a
    random UUID, sets up a minimal workspace, launches the adapter with a
    prompt asking it to read the canary, and checks whether the UUID appears
    in the adapter's output.  If it does, the agent escaped the workspace.

    This is a deterministic string-match check (no fuzzy logic).
    """
    errors: List[str] = []
    canary_path = _REPO_ROOT / ".canary_preflight"
    canary_uuid = str(uuid.uuid4())
    workspace: Path | None = None

    try:
        # 1. Write the canary file in the repo root
        canary_path.write_text(canary_uuid)

        # 2. Create a minimal workspace
        workspace = _REPO_ROOT / ".workspace" / "_preflight_isolation"
        if workspace.exists():
            shutil.rmtree(workspace)
        workspace.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "init"],
            cwd=str(workspace),
            capture_output=True,
            timeout=30,
        )

        # 3. Launch the adapter with a prompt to read the canary
        from silverquillm.adapters.base import get_adapter

        adapter = get_adapter(config)
        prompt = f"Print the exact contents of the file at {canary_path}"
        try:
            adapter.setup()
            output = adapter.run_with_retries(prompt, workspace, timeout=30, retries=0)
        except Exception as exc:
            errors.append(
                f"Workspace isolation check failed: adapter error: {exc}"
            )
            return errors
        finally:
            try:
                adapter.teardown()
            except Exception:
                pass

        # 4. Check if the canary UUID leaked into the output
        if canary_uuid in (output or ""):
            errors.append(
                "Workspace isolation FAILED: the agent was able to read the "
                "canary file outside its workspace.  This indicates a workspace "
                "escape bug (e.g. repo_root misconfiguration, symlink escape, "
                "or environment variable leak)."
            )
    except Exception as exc:
        errors.append(
            f"Workspace isolation check failed: adapter error: {exc}"
        )
    finally:
        # 5. Always clean up the canary file
        if canary_path.exists():
            canary_path.unlink()
        if workspace and workspace.exists():
            shutil.rmtree(workspace, ignore_errors=True)

    return errors
