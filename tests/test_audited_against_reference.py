"""Test harness: run audited tests against Test Oracle Implementations.

For each card in the test oracle workspace that has:
  1. A non-stub oracle impl at test_oracle_workspace/cards/sos/{cn}/card_impl.py
  2. A corresponding audited test at data/tests/audited/sos/{cn}/tests.py

...this module runs the audited tests against the oracle impl using the same
temp-dir mechanism as silverquillm/evaluator.py:run_audited_eval_per_card.

The oracle impl is copied as card_impl.py into a temp dir on PYTHONPATH so
that the audited conftest's _has_explicit_card_impl() returns True and skips
synthetic injection.

Historical SOS discovery keeps its staged authoring behavior. Every selected
HOB card is always validated; a missing implementation or suite is a failure.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from scripts.oracle_support import load_layout, readiness_errors

# Paths relative to repo root
_REPO_ROOT = Path(__file__).resolve().parent.parent
_BENCHMARK_DIR = _REPO_ROOT / "benchmarks" / "sos"
_ORACLE_WORKSPACE = _BENCHMARK_DIR / "data" / "test_oracle_workspace"
_AUDITED_DIR = _BENCHMARK_DIR / "data" / "tests" / "audited" / "sos"
_ORACLE_CARDS_DIR = _ORACLE_WORKSPACE / "cards" / "sos"

# The 10 audited cards for this phase
_AUDITED_CARDS = [
    "sos_1",
    "sos_4",
    "sos_13",
    "sos_57",
    "sos_97",
    "sos_120",
    "sos_201",
    "sos_226",
    "sos_245",
    "sos_257",
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
            if isinstance(
                item, (_ast.FunctionDef, _ast.AsyncFunctionDef)
            ) and not item.name.startswith("__"):
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


def _run_audited_tests_against_oracle(
    cn: str, benchmark: str = "sos", *, impl_suffix: str = ""
) -> tuple[int, str, str]:
    """Run audited tests for a card against its oracle impl.

    *impl_suffix* is appended to the oracle impl, so a test can rebind the card
    class to a variant that decomposes the same behavior differently.

    Returns (returncode, stdout, stderr).
    """
    if benchmark == "sos":
        oracle_workspace, audited_dir = _ORACLE_WORKSPACE, _AUDITED_DIR
        impl_path = _ORACLE_CARDS_DIR / cn / "card_impl.py"
        tests_path = audited_dir / cn / "tests.py"
    else:
        layout = load_layout(_REPO_ROOT, benchmark, require_cards=True)
        errors = readiness_errors(layout, cn)
        if errors:
            return 1, "\n".join(errors), ""
        oracle_workspace, audited_dir = layout.oracle, layout.audited
        impl_path, tests_path = layout.implementation(cn), layout.suite(cn)

    tmp_dir = tempfile.mkdtemp(prefix=f"oracle_{cn}_")
    try:
        tmp = Path(tmp_dir)

        # Copy oracle impl as card_impl.py
        shutil.copy2(impl_path, tmp / "card_impl.py")
        if impl_suffix:
            with open(tmp / "card_impl.py", "a") as impl:
                impl.write(impl_suffix)

        # Copy test_utils.py from oracle workspace
        oracle_test_utils = oracle_workspace / "test_utils.py"
        if oracle_test_utils.exists():
            shutil.copy2(oracle_test_utils, tmp / "test_utils.py")

        # Copy audited tests
        shutil.copy2(tests_path, tmp / "tests.py")

        # Copy conftest from audited dir
        conftest = audited_dir / "conftest.py"
        if conftest.exists():
            shutil.copy2(conftest, tmp / "conftest.py")

        # Build PYTHONPATH: tmp first (card_impl.py), then oracle engine parent,
        # then repo root
        engine_parent = str(oracle_workspace)
        env = dict(__import__("os").environ)
        existing = env.get("PYTHONPATH", "")
        parts = [str(tmp), engine_parent, str(_REPO_ROOT)]
        if existing:
            parts.append(existing)
        env["PYTHONPATH"] = ":".join(parts)

        cmd = [
            sys.executable,
            "-m",
            "pytest",
            str(tmp / "tests.py"),
            "--tb=short",
            "-q",
            "--no-header",
        ]

        result = subprocess.run(
            cmd,
            check=False,
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
_hob_layout = load_layout(_REPO_ROOT, "hob-medium", require_cards=True)
_cases = [pytest.param("sos", card, id=f"sos/{card}") for card in _oracle_cards]
_cases += [pytest.param("hob-medium", card, id=f"hob-medium/{card}") for card in _hob_layout.cards]


@pytest.mark.parametrize("benchmark,cn", _cases)
def test_oracle_impl_passes_audited_tests(benchmark: str, cn: str) -> None:
    """Every selected HOB card is checked, including missing/stub/empty cases."""
    returncode, stdout, stderr = _run_audited_tests_against_oracle(cn, benchmark)
    assert returncode == 0, f"Oracle {benchmark}/{cn} failed:\n{stdout}\n{stderr}"


def test_hob_oracle_cases_cover_the_selected_pool() -> None:
    assert len(_hob_layout.cards) == len(set(_hob_layout.cards))
    assert set(_hob_layout.cards) == {"hob_12", "hob_36", "hob_70", "hob_131", "hob_169"}


# Rule 601.2c lets a spell with a variable number of targets announce how many
# before choosing them, so an implementation may ask for the count as its own
# Player Query. The audited suite must accept that decomposition too.
_ASKS_TARGET_COUNT_FIRST = """

from dataclasses import replace as _replace

from engine.card_queries import choose_number as _choose_number


class _AsksTargetCountFirst(TheEaglesAreComing):
    def get_targets(self, game):
        requirements = super().get_targets(game)
        if not self.kicked:
            return requirements
        count = _choose_number(
            game, self.controller, 0, len(requirements), "How many targets?", source_card=self
        )
        return [_replace(r, optional=False) for r in requirements[:count]]


TheEaglesAreComing = _AsksTargetCountFirst
"""


def test_hob_12_suite_accepts_asking_the_target_count_first() -> None:
    returncode, stdout, stderr = _run_audited_tests_against_oracle(
        "hob_12", "hob-medium", impl_suffix=_ASKS_TARGET_COUNT_FIRST
    )
    assert returncode == 0, f"hob_12 count-first variant failed:\n{stdout}\n{stderr}"
