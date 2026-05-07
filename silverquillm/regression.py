"""Regression test runner for cross-card validation.

After each card's test-informed phase completes, re-run all previously
completed cards' tests against the current persistent engine state.
This detects when engine modifications for one card break earlier cards.

Public API:
- ``RegressionResult`` — per-card regression outcome dataclass.
- ``run_regressions`` — run all previous cards' tests, return results.
- ``regression_feedback_prompt`` — format failures for agent correction.
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
from typing import Any

logger = logging.getLogger(__name__)

__all__ = [
    "CardRegressionResult",
    "RegressionResult",
    "run_regressions",
    "regression_feedback_prompt",
]


@dataclass
class CardRegressionResult:
    """Regression test result for a single previously-completed card."""

    card_id: str
    passed: bool
    tests_file: str
    num_passed: int = 0
    num_failed: int = 0
    num_errors: int = 0
    failure_summary: str = ""
    failed_tests: list[str] = field(default_factory=list)


@dataclass
class RegressionResult:
    """Aggregate regression results across all previously-completed cards."""

    card_results: list[CardRegressionResult] = field(default_factory=list)
    total_cards: int = 0
    cards_passed: int = 0
    cards_failed: int = 0

    @property
    def has_failures(self) -> bool:
        """Return True if any card had regression failures."""
        return self.cards_failed > 0

    @property
    def failed_cards(self) -> list[CardRegressionResult]:
        """Return list of cards that had regression failures."""
        return [cr for cr in self.card_results if not cr.passed]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict for JSON storage."""
        return {
            "total_cards": self.total_cards,
            "cards_passed": self.cards_passed,
            "cards_failed": self.cards_failed,
            "card_results": [
                {
                    "card_id": cr.card_id,
                    "passed": cr.passed,
                    "tests_file": cr.tests_file,
                    "num_passed": cr.num_passed,
                    "num_failed": cr.num_failed,
                    "num_errors": cr.num_errors,
                    "failure_summary": cr.failure_summary,
                    "failed_tests": cr.failed_tests,
                }
                for cr in self.card_results
            ],
        }


@dataclass
class CompletedCard:
    """Descriptor for a previously-completed card whose tests can be re-run."""

    card_id: str
    workspace: Path
    tests_file: Path
    impl_file: Path | None = None


def _parse_failed_tests(stdout: str) -> list[str]:
    """Extract individual failing test names from pytest -v output.

    Looks for lines like ``test_file.py::TestClass::test_method FAILED``.

    Returns
    -------
    list[str]
        List of failing test identifiers.
    """
    failed: list[str] = []
    for line in stdout.splitlines():
        m = re.match(r"^(.*::.*)\s+FAILED\s*$", line.strip())
        if m:
            failed.append(m.group(1).strip())
    return failed


def _build_regression_workspace(
    card: CompletedCard,
    run_engine_dir: Path,
) -> Path:
    """Create a temporary workspace combining current engine with card artifacts.

    Parameters
    ----------
    card:
        Completed card with impl_file and tests_file paths.
    run_engine_dir:
        Path to the current persistent engine directory.

    Returns
    -------
    Path
        Path to the temporary regression workspace.
    """
    tmp_ws = Path(tempfile.mkdtemp(prefix=f"regression_{card.card_id}_"))

    # Copy current engine into workspace
    engine_dst = tmp_ws / "engine"
    if run_engine_dir.exists():
        shutil.copytree(run_engine_dir, engine_dst)

    # Copy test file
    if card.tests_file.exists():
        dst_test = tmp_ws / card.tests_file.name
        shutil.copy2(card.tests_file, dst_test)

    # Copy impl file if available
    if card.impl_file and card.impl_file.exists():
        dst_impl = tmp_ws / card.impl_file.name
        shutil.copy2(card.impl_file, dst_impl)

    return tmp_ws


def _run_card_tests(
    card: CompletedCard,
    timeout: int = 60,
    run_engine_dir: Path | None = None,
) -> CardRegressionResult:
    """Run a single card's tests and return the result.

    Parameters
    ----------
    card:
        Completed card descriptor with workspace and test file paths.
    timeout:
        Maximum seconds to allow for pytest execution.
    run_engine_dir:
        Optional path to current persistent engine directory.  When provided,
        a temporary regression workspace is built combining the current engine
        with the card's saved artifacts, rather than using the card's original
        workspace (which may be stale or cleaned up).

    Returns
    -------
    CardRegressionResult
    """
    tests_path = card.tests_file
    workspace = card.workspace
    tmp_ws: Path | None = None

    # Build a fresh workspace with current engine if run_engine_dir provided
    if run_engine_dir is not None:
        tmp_ws = _build_regression_workspace(card, run_engine_dir)
        workspace = tmp_ws
        # Use the test file inside the temp workspace
        tests_path = tmp_ws / card.tests_file.name

    if not tests_path.exists():
        if tmp_ws is not None:
            shutil.rmtree(tmp_ws, ignore_errors=True)
        return CardRegressionResult(
            card_id=card.card_id,
            passed=True,
            tests_file=str(card.tests_file),
            failure_summary="no test file found; skipped",
        )

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(tests_path), "-v", "--tb=short"],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        if tmp_ws is not None:
            shutil.rmtree(tmp_ws, ignore_errors=True)
        return CardRegressionResult(
            card_id=card.card_id,
            passed=False,
            tests_file=str(card.tests_file),
            failure_summary="pytest timed out",
        )
    except Exception as exc:  # noqa: BLE001
        if tmp_ws is not None:
            shutil.rmtree(tmp_ws, ignore_errors=True)
        return CardRegressionResult(
            card_id=card.card_id,
            passed=False,
            tests_file=str(card.tests_file),
            failure_summary=f"subprocess error: {exc}",
        )

    passed = result.returncode == 0
    num_passed, num_failed, num_errors = _parse_pytest_summary(result.stdout)
    failed_tests = _parse_failed_tests(result.stdout)
    failure_summary = ""
    if not passed:
        # Capture the last portion of stdout+stderr as summary
        combined = (result.stdout + "\n" + result.stderr).strip()
        # Take the last 500 chars as a reasonable summary
        failure_summary = combined[-500:] if len(combined) > 500 else combined

    # Clean up temp workspace
    if tmp_ws is not None:
        shutil.rmtree(tmp_ws, ignore_errors=True)

    return CardRegressionResult(
        card_id=card.card_id,
        passed=passed,
        tests_file=str(card.tests_file),
        num_passed=num_passed,
        num_failed=num_failed,
        num_errors=num_errors,
        failure_summary=failure_summary,
        failed_tests=failed_tests,
    )


def _parse_pytest_summary(stdout: str) -> tuple[int, int, int]:
    """Parse pytest output for passed/failed/error counts.

    Returns
    -------
    tuple[int, int, int]
        (passed, failed, errors)
    """
    passed = failed = errors = 0

    # Match patterns like "3 passed", "1 failed", "2 error"
    for line in stdout.splitlines():
        m_passed = re.search(r"(\d+) passed", line)
        m_failed = re.search(r"(\d+) failed", line)
        m_errors = re.search(r"(\d+) error", line)

        if m_passed:
            passed = int(m_passed.group(1))
        if m_failed:
            failed = int(m_failed.group(1))
        if m_errors:
            errors = int(m_errors.group(1))

    return passed, failed, errors


def run_regressions(
    completed_cards: list[CompletedCard],
    timeout: int = 60,
    run_engine_dir: Path | None = None,
) -> RegressionResult:
    """Run regression tests for all previously-completed cards.

    Parameters
    ----------
    completed_cards:
        List of completed card descriptors.  Each must have ``card_id``,
        ``workspace``, and ``tests_file`` attributes.
    timeout:
        Max seconds per card's pytest invocation.
    run_engine_dir:
        Optional path to the current persistent engine directory.  When
        provided, each card's tests are run in a fresh temporary workspace
        built from the current engine plus the card's saved artifacts,
        rather than from the card's original workspace.

    Returns
    -------
    RegressionResult
        Aggregate results with per-card breakdown.
    """
    if not completed_cards:
        return RegressionResult()

    card_results: list[CardRegressionResult] = []
    for card in completed_cards:
        cr = _run_card_tests(card, timeout=timeout, run_engine_dir=run_engine_dir)
        card_results.append(cr)
        if cr.passed:
            logger.info("Regression OK: card %s", card.card_id)
        else:
            logger.warning(
                "Regression FAIL: card %s — %s",
                card.card_id,
                cr.failure_summary[:200],
            )

    cards_passed = sum(1 for cr in card_results if cr.passed)
    cards_failed = len(card_results) - cards_passed

    return RegressionResult(
        card_results=card_results,
        total_cards=len(card_results),
        cards_passed=cards_passed,
        cards_failed=cards_failed,
    )


def regression_feedback_prompt(regression_result: RegressionResult) -> str:
    """Build a prompt describing regression failures for the agent.

    Parameters
    ----------
    regression_result:
        The regression result containing failure details.

    Returns
    -------
    str
        A prompt string suitable for feeding back to the agent.
    """
    if not regression_result.has_failures:
        return ""

    lines = [
        "## Regression Test Failures",
        "",
        "Your changes broke tests for previously-completed cards.",
        "Please fix the regressions without breaking the current card's tests.",
        "",
    ]

    for cr in regression_result.failed_cards:
        lines.append(f"### Card {cr.card_id}")
        lines.append(f"- Tests file: {cr.tests_file}")
        lines.append(f"- Passed: {cr.num_passed}, Failed: {cr.num_failed}, Errors: {cr.num_errors}")
        if cr.failed_tests:
            lines.append("- Failing tests:")
            for test_name in cr.failed_tests:
                lines.append(f"  - {test_name}")
        if cr.failure_summary:
            lines.append("- Failure details:")
            lines.append("```")
            lines.append(cr.failure_summary)
            lines.append("```")
        lines.append("")

    lines.append("Fix these regressions while keeping the current card's tests passing.")

    return "\n".join(lines)
