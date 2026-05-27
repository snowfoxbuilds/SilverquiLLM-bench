"""Test harness: run audited tests against Test Oracle Implementations.

For each card in the test oracle workspace that has:
  1. A non-stub oracle impl at test_oracle_workspace/cards/sos/{cn}/card_impl.py
  2. A corresponding audited test at data/tests/audited/sos/{cn}/tests.py

...this module runs the audited tests against the oracle impl using the same
temp-dir mechanism as silverquillm/evaluator.py:run_audited_eval_per_card.

The oracle impl is copied as card_impl.py into a temp dir on PYTHONPATH so
that the audited conftest's _has_explicit_card_impl() returns True and skips
synthetic injection.

With empty stubs (no real oracle implementations), no tests are generated
and pytest exits 0.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

# Paths relative to repo root
_REPO_ROOT = Path(__file__).resolve().parent.parent
_BENCHMARK_DIR = _REPO_ROOT / "benchmarks" / "sos"
_ORACLE_WORKSPACE = _BENCHMARK_DIR / "data" / "test_oracle_workspace"
_AUDITED_DIR = _BENCHMARK_DIR / "data" / "tests" / "audited" / "sos"
_ORACLE_CARDS_DIR = _ORACLE_WORKSPACE / "cards" / "sos"

# The 10 audited cards for this phase
_AUDITED_CARDS = [
    "sos_1", "sos_4", "sos_13", "sos_57", "sos_97",
    "sos_120", "sos_201", "sos_226", "sos_245", "sos_257",
]


def _is_stub_impl(impl_path: Path) -> bool:
    """Return True if the card_impl.py is just a stub with no real logic.

    A stub is a file where no class defines a non-dunder method.  The presence
    of any non-dunder method (e.g. on_resolve, can_cast, etc.) — even with a
    trivial body — indicates a real implementation attempt.  ``__init__`` with
    attribute assignments is considered metadata setup, not game logic.
    """
    import ast as _ast

    if not impl_path.exists():
        return True
    content = impl_path.read_text()
    try:
        tree = _ast.parse(content)
    except SyntaxError:
        return True  # Unparseable files are treated as stubs

    for node in _ast.walk(tree):
        if not isinstance(node, _ast.ClassDef):
            continue
        # Check if this class defines any non-dunder method
        for item in node.body:
            if isinstance(item, (_ast.FunctionDef, _ast.AsyncFunctionDef)):
                if not item.name.startswith("__"):
                    return False  # Has a real game-logic method

    return True


def _discover_oracle_cards() -> list[str]:
    """Discover cards that have both a non-stub oracle impl and audited tests."""
    cards = []
    for cn in _AUDITED_CARDS:
        impl_path = _ORACLE_CARDS_DIR / cn / "card_impl.py"
        tests_path = _AUDITED_DIR / cn / "tests.py"
        if impl_path.exists() and tests_path.exists() and not _is_stub_impl(impl_path):
            cards.append(cn)
    return cards


def _run_audited_tests_against_oracle(cn: str) -> tuple[int, str, str]:
    """Run audited tests for a card against its oracle impl.

    Returns (returncode, stdout, stderr).
    """
    impl_path = _ORACLE_CARDS_DIR / cn / "card_impl.py"
    tests_path = _AUDITED_DIR / cn / "tests.py"

    tmp_dir = tempfile.mkdtemp(prefix=f"oracle_{cn}_")
    try:
        tmp = Path(tmp_dir)

        # Copy oracle impl as card_impl.py
        shutil.copy2(impl_path, tmp / "card_impl.py")

        # Copy test_utils.py from oracle workspace
        oracle_test_utils = _ORACLE_WORKSPACE / "test_utils.py"
        if oracle_test_utils.exists():
            shutil.copy2(oracle_test_utils, tmp / "test_utils.py")

        # Copy audited tests
        shutil.copy2(tests_path, tmp / "tests.py")

        # Copy conftest from audited dir
        conftest = _AUDITED_DIR / "conftest.py"
        if conftest.exists():
            shutil.copy2(conftest, tmp / "conftest.py")

        # Build PYTHONPATH: tmp first (card_impl.py), then oracle engine parent,
        # then repo root
        engine_parent = str(_ORACLE_WORKSPACE)
        env = dict(__import__("os").environ)
        existing = env.get("PYTHONPATH", "")
        parts = [str(tmp), engine_parent, str(_REPO_ROOT)]
        if existing:
            parts.append(existing)
        env["PYTHONPATH"] = ":".join(parts)

        cmd = [
            sys.executable, "-m", "pytest",
            str(tmp / "tests.py"),
            "--tb=short", "-q", "--no-header",
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
        )
        return result.returncode, result.stdout, result.stderr
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Parametrized test — one test per oracle card with non-stub impl
# ---------------------------------------------------------------------------

_oracle_cards = _discover_oracle_cards()


@pytest.mark.parametrize("cn", _oracle_cards if _oracle_cards else [pytest.param("_skip_", marks=pytest.mark.skip(reason="No oracle impls ready yet"))])
def test_oracle_impl_passes_audited_tests(cn: str) -> None:
    """Run audited tests against the oracle impl for card {cn}."""
    if cn == "_skip_":
        return

    returncode, stdout, stderr = _run_audited_tests_against_oracle(cn)
    if returncode != 0:
        msg = (
            f"Audited tests FAILED for oracle impl {cn}.\n"
            f"--- stdout ---\n{stdout}\n"
            f"--- stderr ---\n{stderr}\n"
        )
        pytest.fail(msg)
