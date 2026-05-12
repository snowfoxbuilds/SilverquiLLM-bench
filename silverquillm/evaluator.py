"""Evaluation runner for benchmark implementations.

Runs implementations against test suites for self-eval, cross-eval,
and audited-eval scenarios.  Each pytest invocation runs in an isolated
subprocess with a configurable timeout.

Public API:
- ``EvalResult`` — dataclass holding per-card evaluation outcomes.
- ``run_tests`` — low-level: execute pytest on an impl + test pair.
- ``run_self_eval`` — run an agent's impls against its own tests.
- ``run_cross_eval`` — run every (impl, test) pair across agents.
- ``run_audited_eval`` — run all agents' impls against gold-standard tests.
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# Repo root — resolved once at import time
_REPO_ROOT = Path(__file__).resolve().parent.parent

__all__ = [
    "EvalResult",
    "run_tests",
    "run_self_eval",
    "run_self_eval_flat",
    "run_cross_eval",
    "run_audited_eval",
    "run_audited_eval_per_card",
]

# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class EvalResult:
    """Outcome of running one implementation against one test suite."""

    card_id: str
    agent: str
    eval_type: str
    blind_passed: int
    blind_failed: int
    blind_total: int
    tested_passed: int
    tested_failed: int
    tested_total: int
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Pytest output parser
# ---------------------------------------------------------------------------

# Matches pytest summary lines like "3 passed, 1 failed" or "5 passed"
_SUMMARY_RE = re.compile(
    r"(?:(\d+)\s+passed)?"
    r"(?:,?\s*(\d+)\s+failed)?"
    r"(?:,?\s*(\d+)\s+error)?"
)


def _parse_pytest_output(output: str) -> tuple[int, int, int, list[str]]:
    """Parse pytest ``-q`` output and return (passed, failed, total, errors).

    Looks for the summary line (e.g. ``3 passed, 1 failed``) and collects
    any FAILED / ERROR lines as error messages.
    """
    passed = 0
    failed = 0
    errors: list[str] = []

    # Collect individual failure/error lines
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("FAILED ") or stripped.startswith("ERROR "):
            errors.append(stripped)

    # Find the short summary line produced by ``pytest -q``
    # Examples:
    #   "3 passed, 1 failed in 0.12s"
    #   "5 passed in 0.05s"
    #   "2 failed in 0.03s"
    for line in output.splitlines():
        # Look for lines containing "passed" or "failed" with counts
        m_passed = re.search(r"(\d+)\s+passed", line)
        m_failed = re.search(r"(\d+)\s+failed", line)
        m_error = re.search(r"(\d+)\s+error", line)
        if m_passed or m_failed or m_error:
            if m_passed:
                passed = int(m_passed.group(1))
            if m_failed:
                failed = int(m_failed.group(1))
            if m_error:
                failed += int(m_error.group(1))
            break

    total = passed + failed
    return passed, failed, total, errors


# ---------------------------------------------------------------------------
# Core test runner
# ---------------------------------------------------------------------------


def run_tests(
    impl_path: Path,
    tests_path: Path,
    timeout: int = 60,
) -> tuple[int, int, int, list[str]]:
    """Run *tests_path* against *impl_path* in an isolated subprocess.

    The implementation file is copied to ``card_impl.py`` in a temporary
    directory so that tests can ``from card_impl import …``.

    Returns ``(passed, failed, total, error_messages)``.
    """
    tmp_dir = tempfile.mkdtemp(prefix="eval_")
    try:
        tmp = Path(tmp_dir)

        # Copy impl as card_impl.py so tests can import it
        shutil.copy2(impl_path, tmp / "card_impl.py")

        # Also copy under alternative names agents might import from
        for alias in ("blind_impl.py", "tested_impl.py"):
            if not (tmp / alias).exists():
                shutil.copy2(impl_path, tmp / alias)

        # Copy test_utils.py so flat imports (from test_utils import ...) work
        test_utils_src = _REPO_ROOT / "tests" / "test_utils.py"
        if test_utils_src.exists():
            shutil.copy2(test_utils_src, tmp / "test_utils.py")

        # Copy tests as test_card.py to avoid shadowing the tests/ package.
        # The agent may write `from tests.test_utils import ...` which fails
        # if a local file named tests.py exists (Python resolves it as the
        # local module instead of the repo's tests/ package).
        shutil.copy2(tests_path, tmp / "test_card.py")

        # PYTHONPATH: temp dir first (card_impl.py, test_utils.py),
        # then repo root (for tests/ package and engine/ imports)
        env = dict(__import__("os").environ)
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(tmp) + ":" + str(_REPO_ROOT) + (":" + existing if existing else "")

        # Run pytest on the RENAMED copy in the temp dir
        cmd = [
            sys.executable,
            "-m",
            "pytest",
            str(tmp / "test_card.py"),
            "--tb=short",
            "-q",
            "--no-header",
        ]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
            )
            combined = result.stdout + "\n" + result.stderr
        except subprocess.TimeoutExpired:
            return 0, 0, 0, [f"Timeout after {timeout}s"]

        return _parse_pytest_output(combined)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# High-level evaluation functions
# ---------------------------------------------------------------------------


def run_self_eval(card_dir: Path, agent_name: str) -> EvalResult:
    """Run *agent_name*'s blind and tested impls against its own tests.

    Expected layout under *card_dir*::

        {agent_name}/
            blind_impl.py
            tested_impl.py
            tests.py
    """
    agent_dir = card_dir / agent_name
    tests_file = agent_dir / "tests.py"
    blind_impl = agent_dir / "blind_impl.py"
    tested_impl = agent_dir / "tested_impl.py"

    all_errors: list[str] = []

    if blind_impl.exists() and tests_file.exists():
        bp, bf, bt, be = run_tests(blind_impl, tests_file)
        all_errors.extend(be)
    else:
        bp, bf, bt = 0, 0, 0
        if not blind_impl.exists():
            all_errors.append(f"Missing {blind_impl}")
        if not tests_file.exists():
            all_errors.append(f"Missing {tests_file}")

    if tested_impl.exists() and tests_file.exists():
        tp, tf, tt, te = run_tests(tested_impl, tests_file)
        all_errors.extend(te)
    else:
        tp, tf, tt = 0, 0, 0
        if not tested_impl.exists():
            all_errors.append(f"Missing {tested_impl}")

    return EvalResult(
        card_id=card_dir.name,
        agent=agent_name,
        eval_type="self",
        blind_passed=bp,
        blind_failed=bf,
        blind_total=bt,
        tested_passed=tp,
        tested_failed=tf,
        tested_total=tt,
        errors=all_errors,
    )


def run_self_eval_flat(card_dir: Path, agent_name: str) -> EvalResult:
    """Run self-eval using the flat card directory layout.

    Unlike :func:`run_self_eval` which expects ``{card_dir}/{agent_name}/``
    subdirectories, this function works with the flat layout produced by
    :func:`~benchmark.results.save_card_result`::

        card_dir/
            blind_impl.py
            tested_impl.py
            tests.py

    Parameters
    ----------
    card_dir:
        Path to the card directory containing impl and test files directly.
    agent_name:
        Name of the agent (used in the returned :class:`EvalResult`).

    Returns
    -------
    EvalResult
        Evaluation outcome for the card.
    """
    tests_file = card_dir / "tests.py"
    blind_impl = card_dir / "blind_impl.py"
    tested_impl = card_dir / "tested_impl.py"

    all_errors: list[str] = []

    if blind_impl.exists() and tests_file.exists():
        bp, bf, bt, be = run_tests(blind_impl, tests_file)
        all_errors.extend(be)
    else:
        bp, bf, bt = 0, 0, 0
        if not blind_impl.exists():
            all_errors.append(f"Missing {blind_impl}")
        if not tests_file.exists():
            all_errors.append(f"Missing {tests_file}")

    if tested_impl.exists() and tests_file.exists():
        tp, tf, tt, te = run_tests(tested_impl, tests_file)
        all_errors.extend(te)
    else:
        tp, tf, tt = 0, 0, 0
        if not tested_impl.exists():
            all_errors.append(f"Missing {tested_impl}")

    return EvalResult(
        card_id=card_dir.name,
        agent=agent_name,
        eval_type="self",
        blind_passed=bp,
        blind_failed=bf,
        blind_total=bt,
        tested_passed=tp,
        tested_failed=tf,
        tested_total=tt,
        errors=all_errors,
    )


def run_cross_eval(card_dir: Path, agents: list[str]) -> list[EvalResult]:
    """Run each agent's impls against every *other* agent's tests.

    Returns ``N × (N-1)`` :class:`EvalResult` objects (one per ordered
    impl_agent / test_agent pair where they differ).
    """
    results: list[EvalResult] = []
    for impl_agent in agents:
        for test_agent in agents:
            if impl_agent == test_agent:
                continue

            impl_dir = card_dir / impl_agent
            test_dir = card_dir / test_agent
            tests_file = test_dir / "tests.py"

            blind_impl = impl_dir / "blind_impl.py"
            tested_impl = impl_dir / "tested_impl.py"

            all_errors: list[str] = []

            if blind_impl.exists() and tests_file.exists():
                bp, bf, bt, be = run_tests(blind_impl, tests_file)
                all_errors.extend(be)
            else:
                bp, bf, bt = 0, 0, 0
                if not blind_impl.exists():
                    all_errors.append(f"Missing {blind_impl}")
                if not tests_file.exists():
                    all_errors.append(f"Missing {tests_file}")

            if tested_impl.exists() and tests_file.exists():
                tp, tf, tt, te = run_tests(tested_impl, tests_file)
                all_errors.extend(te)
            else:
                tp, tf, tt = 0, 0, 0
                if not tested_impl.exists():
                    all_errors.append(f"Missing {tested_impl}")

            results.append(
                EvalResult(
                    card_id=card_dir.name,
                    agent=impl_agent,
                    eval_type=f"cross:{test_agent}",
                    blind_passed=bp,
                    blind_failed=bf,
                    blind_total=bt,
                    tested_passed=tp,
                    tested_failed=tf,
                    tested_total=tt,
                    errors=all_errors,
                )
            )
    return results


def run_audited_eval(
    card_dir: Path,
    agents: list[str],
    audited_tests: Path,
) -> list[EvalResult]:
    """Run all agents' impls against gold-standard *audited_tests*.

    Returns one :class:`EvalResult` per agent.
    """
    results: list[EvalResult] = []
    for agent_name in agents:
        agent_dir = card_dir / agent_name
        blind_impl = agent_dir / "blind_impl.py"
        tested_impl = agent_dir / "tested_impl.py"

        all_errors: list[str] = []

        if blind_impl.exists() and audited_tests.exists():
            bp, bf, bt, be = run_tests(blind_impl, audited_tests)
            all_errors.extend(be)
        else:
            bp, bf, bt = 0, 0, 0
            if not blind_impl.exists():
                all_errors.append(f"Missing {blind_impl}")
            if not audited_tests.exists():
                all_errors.append(f"Missing {audited_tests}")

        if tested_impl.exists() and audited_tests.exists():
            tp, tf, tt, te = run_tests(tested_impl, audited_tests)
            all_errors.extend(te)
        else:
            tp, tf, tt = 0, 0, 0
            if not tested_impl.exists():
                all_errors.append(f"Missing {tested_impl}")

        results.append(
            EvalResult(
                card_id=card_dir.name,
                agent=agent_name,
                eval_type="audited",
                blind_passed=bp,
                blind_failed=bf,
                blind_total=bt,
                tested_passed=tp,
                tested_failed=tf,
                tested_total=tt,
                errors=all_errors,
            )
        )
    return results


def run_audited_eval_per_card(
    impl_path: Path,
    card_id: str,
    audited_dir: Path,
    timeout: int = 60,
) -> tuple[int, int, int, list[str]]:
    """Run per-card audited tests against an implementation.

    Discovers the audited test file at ``{audited_dir}/{card_id}/tests.py``
    and runs it against *impl_path* in an isolated temp directory.

    The implementation is copied as ``card_impl.py`` and the per-card
    ``tests.py`` is copied alongside it so that ``from card_impl import …``
    resolves correctly.

    The audited conftest (``{audited_dir}/conftest.py``) is also copied into
    the flat temp directory.  The conftest's synthetic ``card_impl`` injection
    is intentionally bypassed here: because ``card_impl.py`` is always present
    on ``PYTHONPATH``, ``_has_explicit_card_impl()`` returns ``True`` and the
    conftest skips injection.  If the conftest were copied without a real
    ``card_impl.py`` present, ``_detect_collector_dir()`` would fail (the flat
    temp dir has no ``audited/<set>/<cn>/`` path structure).  This invariant is
    enforced by the assertion below.

    Parameters
    ----------
    impl_path:
        Path to the agent's implementation file (e.g. ``tested_impl.py``).
    card_id:
        The collector number / key used to locate the per-card test directory.
    audited_dir:
        Root directory containing per-card subdirectories with ``tests.py``.
    timeout:
        Subprocess timeout in seconds.

    Returns
    -------
    tuple of (passed, failed, total, errors)
        Same shape as :func:`run_tests`.
    """
    tests_file = audited_dir / card_id / "tests.py"
    if not tests_file.exists():
        return 0, 0, 0, [f"No audited tests found at {tests_file}"]

    if not impl_path.exists():
        return 0, 0, 0, [f"Missing implementation: {impl_path}"]

    tmp_dir = tempfile.mkdtemp(prefix="eval_percard_")
    try:
        tmp = Path(tmp_dir)

        # Copy impl as card_impl.py — MUST happen before conftest is copied so
        # _has_explicit_card_impl() returns True and the conftest skips injection.
        shutil.copy2(impl_path, tmp / "card_impl.py")
        assert (tmp / "card_impl.py").exists(), (
            "card_impl.py must be present before conftest is copied; "
            "the conftest relies on its presence to skip synthetic injection"
        )

        # Copy the per-card tests.py into the temp directory
        shutil.copy2(tests_file, tmp / "tests.py")

        # Also copy conftest.py from audited_dir if present (for shared fixtures)
        conftest = audited_dir / "conftest.py"
        if conftest.exists():
            shutil.copy2(conftest, tmp / "conftest.py")

        # Run pytest on the copied tests.py in the temp directory
        env = dict(__import__("os").environ)
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(tmp) + ":" + str(_REPO_ROOT) + (":" + existing if existing else "")

        cmd = [
            sys.executable,
            "-m",
            "pytest",
            str(tmp / "tests.py"),
            "--tb=short",
            "-q",
            "--no-header",
        ]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
            )
            combined = result.stdout + "\n" + result.stderr
        except subprocess.TimeoutExpired:
            return 0, 0, 0, [f"Timeout after {timeout}s"]

        return _parse_pytest_output(combined)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
