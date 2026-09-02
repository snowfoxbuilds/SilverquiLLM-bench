"""Evaluation runner for benchmark implementations.

Three post-run scoring dimensions, all using audited tests:

**Dimension 1 — SOS Card Correctness:**
  For each completed SOS card, run audited tests against the agent's card_impl.py
  with the agent's engine modifications.

**Dimension 2 — FDN Card Regression:**
  For each FDN card with audited tests, run them against the pre-filled reference
  card_impl.py using the agent's engine modifications. Failures indicate the
  agent's engine changes broke existing card behavior.

**Dimension 3 — Engine Regression:**
  Run core engine tests against the agent's engine_work/. Failures indicate
  the agent broke fundamental game mechanics.

Legacy API (``run_tests``, ``run_self_eval``, ``run_cross_eval``,
``run_audited_eval``, ``run_audited_eval_per_card``) is retained for
backward compatibility.

Public API:
- ``evaluate`` — run all three scoring dimensions and return an ``FullEvalResult``.
- ``CardResult`` / ``EngineResult`` / ``FullEvalResult`` — result dataclasses.
- ``EvalResult`` — legacy per-card evaluation outcome (v1 schema).
- ``run_tests`` — low-level: execute pytest on an impl + test pair.
- ``run_self_eval`` — run an agent's impls against its own tests.
- ``run_cross_eval`` — run every (impl, test) pair across agents.
- ``run_audited_eval`` — run all agents' impls against gold-standard tests.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from silverquillm.jobdir import BenchmarkRef

logger = logging.getLogger(__name__)

# Repo root — resolved once at import time
_REPO_ROOT = Path(__file__).resolve().parent.parent

__all__ = [
    "CardResult",
    "EngineResult",
    "EnginePatchError",
    "EvalPaths",
    "EvalResult",
    "FullEvalResult",
    "evaluate",
    "evaluate_run",
    "resolve_eval_paths",
    "run_tests",
    "run_self_eval",
    "run_self_eval_flat",
    "run_cross_eval",
    "run_audited_eval",
    "run_audited_eval_per_card",
]

# ---------------------------------------------------------------------------
# Result dataclasses — new 3-dimension schema
# ---------------------------------------------------------------------------


@dataclass
class CardResult:
    """Result of running audited tests for a single card."""

    collector_number: str
    tests_passed: int = 0
    tests_failed: int = 0
    tests_total: int = 0
    pass_rate: float = 0.0
    errors: list[str] = field(default_factory=list)
    skipped: bool = False
    test_nodes: list[dict] = field(default_factory=list)
    tests_hash: str = ""


@dataclass
class EngineResult:
    """Result of running core engine tests."""

    tests_passed: int = 0
    tests_failed: int = 0
    tests_total: int = 0
    pass_rate: float = 0.0
    errors: list[str] = field(default_factory=list)


@dataclass
class FullEvalResult:
    """Aggregated result across all three evaluation dimensions."""

    sos_results: dict[str, CardResult] = field(default_factory=dict)
    fdn_results: dict[str, CardResult] = field(default_factory=dict)
    engine_result: EngineResult = field(default_factory=EngineResult)

    # Aggregate scores
    sos_pass_rate: float = 0.0
    fdn_pass_rate: float = 0.0
    engine_pass_rate: float = 0.0

    def compute_aggregates(self) -> None:
        """Recompute aggregate pass rates from per-card/engine results."""
        # SOS aggregate
        sos_passed = sum(r.tests_passed for r in self.sos_results.values())
        sos_total = sum(r.tests_total for r in self.sos_results.values())
        self.sos_pass_rate = sos_passed / sos_total if sos_total > 0 else 0.0

        # FDN aggregate
        fdn_passed = sum(r.tests_passed for r in self.fdn_results.values())
        fdn_total = sum(r.tests_total for r in self.fdn_results.values())
        self.fdn_pass_rate = fdn_passed / fdn_total if fdn_total > 0 else 0.0

        # Engine aggregate
        self.engine_pass_rate = self.engine_result.pass_rate


# ---------------------------------------------------------------------------
# Legacy result dataclasses (v1 schema — retained for backward compat)
# ---------------------------------------------------------------------------


@dataclass
class EvalResult:
    """Outcome of running one implementation against one test suite (v1 schema).

    Retained for backward compatibility with existing evaluation functions
    (``run_self_eval``, ``run_cross_eval``, ``run_audited_eval``) and tests.
    """

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
    engine_dir: Path | None = None,
) -> tuple[int, int, int, list[str]]:
    """Run *tests_path* against *impl_path* in an isolated subprocess.

    The implementation file is copied to ``card_impl.py`` in a temporary
    directory so that tests can ``from card_impl import …``.

    Parameters
    ----------
    engine_dir:
        Optional path to an engine directory.  When provided it is prepended
        to ``PYTHONPATH`` so that ``import engine as engine`` resolves to this directory's
        parent (i.e. the run-level engine state rather than the repo default).

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
        test_utils_src = _REPO_ROOT / "benchmarks" / "sos" / "workspace" / "test_utils.py"
        if test_utils_src.exists():
            shutil.copy2(test_utils_src, tmp / "test_utils.py")

        # Copy tests as test_card.py to avoid shadowing the tests/ package.
        # The agent may write `from test_utils import ...` which fails
        # if a local file named tests.py exists (Python resolves it as the
        # local module instead of the repo's tests/ package).
        shutil.copy2(tests_path, tmp / "test_card.py")

        # PYTHONPATH: temp dir first (card_impl.py, test_utils.py),
        # then engine dir parent (if provided, for run-level engine state),
        # then repo root (for tests/ package and engine/ imports)
        pythonpath_parts = [str(tmp)]
        if engine_dir is not None:
            # engine_dir is e.g. run_dir/engine; its parent must be on
            # PYTHONPATH so ``import engine as engine`` resolves to the run-level copy.
            pythonpath_parts.append(str(Path(engine_dir).parent))
        pythonpath_parts.append(str(_REPO_ROOT))

        # Run pytest on the RENAMED copy in the temp dir
        return _run_pytest_with_pythonpath(
            tmp / "test_card.py", pythonpath_parts, timeout=timeout
        )
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# High-level evaluation functions
# ---------------------------------------------------------------------------


def _eval_impl_pair(
    *,
    card_id: str,
    agent: str,
    eval_type: str,
    blind_impl: Path,
    tested_impl: Path,
    tests_file: Path,
) -> EvalResult:
    """Run a blind/tested impl pair against *tests_file* into an EvalResult.

    Shared core of :func:`run_self_eval`, :func:`run_self_eval_flat`,
    :func:`run_cross_eval` and :func:`run_audited_eval` — those differ only in
    how ``blind_impl`` / ``tested_impl`` / ``tests_file`` and ``eval_type`` are
    derived. A missing impl or test file yields zero counts plus a ``Missing
    {path}`` error rather than raising.
    """
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
        card_id=card_id,
        agent=agent,
        eval_type=eval_type,
        blind_passed=bp,
        blind_failed=bf,
        blind_total=bt,
        tested_passed=tp,
        tested_failed=tf,
        tested_total=tt,
        errors=all_errors,
    )


def run_self_eval(card_dir: Path, agent_name: str) -> EvalResult:
    """Run *agent_name*'s blind and tested impls against its own tests.

    Expected layout under *card_dir*::

        {agent_name}/
            blind_impl.py
            tested_impl.py
            tests.py
    """
    agent_dir = card_dir / agent_name
    return _eval_impl_pair(
        card_id=card_dir.name,
        agent=agent_name,
        eval_type="self",
        blind_impl=agent_dir / "blind_impl.py",
        tested_impl=agent_dir / "tested_impl.py",
        tests_file=agent_dir / "tests.py",
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
    return _eval_impl_pair(
        card_id=card_dir.name,
        agent=agent_name,
        eval_type="self",
        blind_impl=card_dir / "blind_impl.py",
        tested_impl=card_dir / "tested_impl.py",
        tests_file=card_dir / "tests.py",
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
            results.append(
                _eval_impl_pair(
                    card_id=card_dir.name,
                    agent=impl_agent,
                    eval_type=f"cross:{test_agent}",
                    blind_impl=impl_dir / "blind_impl.py",
                    tested_impl=impl_dir / "tested_impl.py",
                    tests_file=test_dir / "tests.py",
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
        results.append(
            _eval_impl_pair(
                card_id=card_dir.name,
                agent=agent_name,
                eval_type="audited",
                blind_impl=agent_dir / "blind_impl.py",
                tested_impl=agent_dir / "tested_impl.py",
                tests_file=audited_tests,
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
        return _run_pytest_with_pythonpath(
            tmp / "tests.py", [str(tmp), str(_REPO_ROOT)], timeout=timeout
        )
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# New 3-dimension evaluation system
# ---------------------------------------------------------------------------


class EnginePatchError(RuntimeError):
    """Raised when ``engine_diff.patch`` cannot be applied to the baseline."""


def _prepare_engine_work(
    run_dir: Path,
    engine_dir: Path,
) -> tuple[Path, Path | None]:
    """Prepare the agent's engine directory for evaluation.

    Always returns a path named ``engine/`` inside a staging directory so
    that putting ``path.parent`` on ``PYTHONPATH`` makes ``import engine as engine``
    resolve correctly.

    Lookup order:

    1. ``run_dir/engine_work/`` — legacy direct copy.
    2. ``run_dir/workspace_final/engine/`` — snapshot fallback per ADR-005.
       This is the authoritative source when present and supersedes the
       diff-and-apply path entirely.
    3. ``run_dir/engine_diff.patch`` — copy *engine_dir* to a staging dir
       and apply the patch with ``-p1`` (patches generated by the harvest
       use ``a/<file>`` / ``b/<file>`` headers).
    4. Otherwise, return *engine_dir* unchanged.

    Returns
    -------
    tuple[Path, Path | None]
        ``(engine_path, staging_dir)`` where *staging_dir* is the temp
        directory to clean up (or ``None`` if no temp dir was created).

    Raises
    ------
    EnginePatchError
        When ``engine_diff.patch`` exists but ``git apply`` rejects it.
        Surfaced loudly to prevent silently scoring against the baseline.
    """
    engine_work = run_dir / "engine_work"
    if engine_work.is_dir():
        # Copy engine_work into a staging dir named "engine/" so that
        # PYTHONPATH=staging_dir makes ``import engine as engine`` work.
        staging = Path(tempfile.mkdtemp(prefix="eval_engine_"))
        shutil.copytree(engine_work, staging / "engine")
        return staging / "engine", staging

    snapshot_engine = run_dir / "workspace_final" / "engine"
    if snapshot_engine.is_dir():
        staging = Path(tempfile.mkdtemp(prefix="eval_engine_"))
        shutil.copytree(snapshot_engine, staging / "engine")
        return staging / "engine", staging

    patch_file = run_dir / "engine_diff.patch"
    if patch_file.is_file():
        staging = Path(tempfile.mkdtemp(prefix="eval_engine_"))
        shutil.copytree(engine_dir, staging / "engine")
        try:
            # Run `git apply` from the staging engine dir so the patch's
            # a/<file> / b/<file> headers (after -p1) resolve to files
            # inside the staging copy. Using cwd= avoids `git apply`'s
            # "invalid path" rejection of absolute --directory targets
            # outside a git working tree.
            subprocess.run(
                ["git", "apply", "-p1", str(patch_file)],
                check=True,
                capture_output=True,
                text=True,
                cwd=str(staging / "engine"),
            )
        except subprocess.CalledProcessError as exc:
            shutil.rmtree(staging, ignore_errors=True)
            raise EnginePatchError(
                f"Failed to apply engine_diff.patch: {exc.stderr.strip()}"
            ) from exc
        return staging / "engine", staging

    # No engine modifications — use the original
    return engine_dir, None


def _generate_report_conftest(report_jsonl_path: str) -> str:
    """Return Python source for a conftest.py that records test outcomes to JSONL.

    The generated conftest uses the ``pytest_runtest_logreport`` hook to capture
    per-test outcomes.  Only ``when == "call"`` reports are recorded for
    pass/fail.  ``when == "setup"`` failures (including collection errors) are
    also captured since those tests never reach ``call``.

    The JSONL file path is baked into the source as a literal string so no
    env-var plumbing is needed.
    """
    # Escape backslashes and quotes in the path for embedding in Python source
    safe_path = report_jsonl_path.replace("\\", "\\\\").replace('"', '\\"')
    return f'''
import json as _json

_REPORT_PATH = "{safe_path}"
_seen_nodes = set()

def pytest_runtest_logreport(report):
    """Record each test node outcome to a JSONL file."""
    nodeid = report.nodeid
    if report.when == "call":
        # Skip xfail/xpass outcomes — they appear as skipped=True in the call phase.
        # Intentionally omit them; only genuine pass/fail outcomes are recorded.
        if report.skipped or hasattr(report, "wasxfail"):
            return
        outcome = "pass" if report.passed else "fail"
        _seen_nodes.add(nodeid)
        with open(_REPORT_PATH, "a") as f:
            f.write(_json.dumps({{"nodeid": nodeid, "when": "call", "outcome": outcome}}) + "\\n")
    elif report.when == "setup" and report.failed:
        # Setup failure — test never reaches "call"
        if nodeid not in _seen_nodes:
            _seen_nodes.add(nodeid)
            with open(_REPORT_PATH, "a") as f:
                f.write(_json.dumps({{"nodeid": nodeid, "when": "setup", "outcome": "fail"}}) + "\\n")

def pytest_collectreport(report):
    """Record collection errors."""
    if report.failed:
        nodeid = report.nodeid or "<collection-error>"
        with open(_REPORT_PATH, "a") as f:
            f.write(_json.dumps({{"nodeid": nodeid, "when": "collect", "outcome": "fail"}}) + "\\n")
'''


def _normalize_nodeid(nodeid: str) -> str:
    """Normalize a pytest node ID to the ``tests.py::test_x`` form.

    Strips any directory prefix so only the filename and test remain.
    For example ``/tmp/eval_sos_abc123/tests.py::test_foo`` becomes
    ``tests.py::test_foo``.
    """
    # Handle path separators — keep only the filename portion
    if "/" in nodeid:
        # Find the last path component before ::
        if "::" in nodeid:
            path_part, rest = nodeid.split("::", 1)
            filename = path_part.rsplit("/", 1)[-1]
            return f"{filename}::{rest}"
        else:
            return nodeid.rsplit("/", 1)[-1]
    return nodeid


def _parse_report_jsonl(report_path: Path) -> list[dict]:
    """Parse the JSONL report file into a list of ``{"test_node": ..., "outcome": ...}`` dicts.

    Deduplicates by nodeid (first occurrence wins).  Normalizes nodeids to
    ``tests.py::test_x`` form.  Collection errors without a real nodeid get
    a synthetic ``tests.py::<collection-error>`` id.
    """
    if not report_path.exists():
        return []

    seen: set[str] = set()
    nodes: list[dict] = []

    for line in report_path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        raw_nodeid = entry.get("nodeid", "")
        outcome = entry.get("outcome")

        # Only accept the explicit values the conftest writes ('pass' / 'fail').
        # Any other or missing outcome is ignored — must not be silently coerced.
        if outcome not in ("pass", "fail"):
            continue

        # Normalize the nodeid
        if raw_nodeid and raw_nodeid != "<collection-error>":
            normalized = _normalize_nodeid(raw_nodeid)
        else:
            normalized = "tests.py::<collection-error>"

        if normalized not in seen:
            seen.add(normalized)
            nodes.append({
                "test_node": normalized,
                "outcome": outcome,
            })

    return nodes


def _restore_conftest(
    conftest_path: Path | None,
    original_content: str | None,
) -> None:
    """Restore or remove the conftest.py after report capture."""
    if conftest_path is None:
        return
    if original_content is not None:
        conftest_path.write_text(original_content)
    elif conftest_path.exists():
        conftest_path.unlink()


def _run_pytest_with_pythonpath(
    test_path: Path,
    pythonpath_parts: list[str],
    timeout: int = 60,
    capture_test_nodes: bool = False,
) -> tuple[int, int, int, list[str]] | tuple[int, int, int, list[str], list[dict]]:
    """Run pytest on *test_path* with a custom PYTHONPATH.

    Returns ``(passed, failed, total, errors)``.  When *capture_test_nodes*
    is ``True``, returns a 5-tuple with an additional list of per-node
    outcome dicts: ``[{"test_node": "tests.py::test_x", "outcome": "pass"|"fail"}, ...]``.
    """
    env = dict(os.environ)
    existing = env.get("PYTHONPATH", "")
    parts = pythonpath_parts + ([existing] if existing else [])
    env["PYTHONPATH"] = ":".join(parts)

    report_jsonl_path = None
    existing_conftest_backup = None
    conftest_in_test_dir = None

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        str(test_path),
        "--tb=short",
        "-q",
        "--no-header",
    ]

    if capture_test_nodes:
        # Write a report JSONL to a temp file; inject conftest into the test's
        # parent directory so pytest picks it up automatically.
        report_jsonl_dir = tempfile.mkdtemp(prefix="eval_report_")
        report_jsonl_path = Path(report_jsonl_dir) / "report.jsonl"
        test_dir = test_path.parent
        conftest_in_test_dir = test_dir / "conftest.py"

        # Back up any existing conftest.py (e.g. from audited tests)
        if conftest_in_test_dir.exists():
            existing_conftest_backup = conftest_in_test_dir.read_text()
            # Prepend report hooks to existing conftest
            report_hooks = _generate_report_conftest(str(report_jsonl_path))
            conftest_in_test_dir.write_text(
                report_hooks + "\n" + existing_conftest_backup
            )
        else:
            conftest_in_test_dir.write_text(
                _generate_report_conftest(str(report_jsonl_path))
            )

    try:
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
            if capture_test_nodes:
                return 0, 0, 0, [f"Timeout after {timeout}s"], []
            return 0, 0, 0, [f"Timeout after {timeout}s"]

        parsed = _parse_pytest_output(combined)

        if capture_test_nodes:
            # test_nodes enumerates only executed pass/fail nodes.  Skipped and
            # xfail tests are intentionally omitted, so len(test_nodes) may be
            # less than tests_total when skips exist.  The authoritative counts
            # (tests_passed, tests_failed, tests_total) come from
            # _parse_pytest_output and are unaffected.
            test_nodes = _parse_report_jsonl(report_jsonl_path) if report_jsonl_path else []
            return parsed[0], parsed[1], parsed[2], parsed[3], test_nodes

        return parsed
    finally:
        # Always restore conftest and clean up the report temp dir, regardless
        # of how the body exits (normal return, TimeoutExpired, or any other
        # exception such as OSError/PermissionError).
        if capture_test_nodes:
            _restore_conftest(conftest_in_test_dir, existing_conftest_backup)
            if report_jsonl_path:
                shutil.rmtree(report_jsonl_path.parent, ignore_errors=True)


def _make_card_result(
    collector_number: str,
    passed: int,
    failed: int,
    total: int,
    errors: list[str],
) -> CardResult:
    """Build a :class:`CardResult` from raw pytest output."""
    return CardResult(
        collector_number=collector_number,
        tests_passed=passed,
        tests_failed=failed,
        tests_total=total,
        pass_rate=passed / total if total > 0 else 0.0,
        errors=errors,
    )


def _eval_sos_cards(
    run_dir: Path,
    cards_dir: Path,
    engine_work: Path,
    audited_dir: Path,
    timeout: int = 60,
) -> dict[str, CardResult]:
    """Dimension 1: SOS Card Correctness.

    For each SOS card where status == 'completed', run audited tests
    against the agent's card_impl.py + engine_work.
    """
    results: dict[str, CardResult] = {}

    # Read status from run_dir
    status_file = run_dir / "status.json"
    if not status_file.exists():
        logger.warning("No status.json found in %s", run_dir)
        return results

    try:
        statuses = json.loads(status_file.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read status.json: %s", exc)
        return results

    cards_status = statuses if isinstance(statuses, dict) else {}

    for cn, info in cards_status.items():
        status = info if isinstance(info, str) else info.get("status", "")
        if status != "completed":
            continue

        # Check for audited tests
        test_file = audited_dir / cn / "tests.py"
        if not test_file.exists():
            results[cn] = CardResult(
                collector_number=cn, skipped=True,
                errors=[f"No audited tests at {test_file}"],
            )
            continue

        # Find agent's card_impl.py
        card_impl = run_dir / "cards" / cn / "card_impl.py"
        if not card_impl.exists():
            results[cn] = CardResult(
                collector_number=cn,
                errors=[f"Missing card_impl.py at {card_impl}"],
            )
            continue

        # Set up temp dir with card_impl.py
        tmp_dir = tempfile.mkdtemp(prefix="eval_sos_")
        try:
            tmp = Path(tmp_dir)
            shutil.copy2(card_impl, tmp / "card_impl.py")
            shutil.copy2(test_file, tmp / "tests.py")
            test_utils_src = _REPO_ROOT / "benchmarks" / "sos" / "data" / "test_oracle_workspace" / "test_utils.py"
            if test_utils_src.exists():
                shutil.copy2(test_utils_src, tmp / "test_utils.py")

            # PYTHONPATH: tmp (card_impl), engine parent, repo root
            pp = [str(tmp)]
            if engine_work.exists():
                pp.append(str(engine_work.parent))
            pp.append(str(_REPO_ROOT))

            passed, failed, total, errors, test_nodes = _run_pytest_with_pythonpath(
                tmp / "tests.py", pp, timeout=timeout,
                capture_test_nodes=True,
            )
            cr = _make_card_result(cn, passed, failed, total, errors)
            cr.test_nodes = test_nodes

            # Stamp tests_hash — SHA-256 of the audited test file bytes
            try:
                cr.tests_hash = hashlib.sha256(test_file.read_bytes()).hexdigest()
            except OSError:
                cr.tests_hash = ""

            results[cn] = cr

            # Write result.json
            result_dir = run_dir / "cards" / cn
            result_dir.mkdir(parents=True, exist_ok=True)
            (result_dir / "result.json").write_text(
                json.dumps(asdict(cr), indent=2)
            )
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    return results


def _eval_fdn_cards(
    cards_dir: Path,
    engine_work: Path,
    audited_dir: Path,
    timeout: int = 60,
) -> dict[str, CardResult]:
    """Dimension 2: FDN Card Regression.

    For each FDN card with audited tests, run them against the pre-filled
    reference card_impl.py using the agent's engine_work.
    """
    results: dict[str, CardResult] = {}

    if not audited_dir.exists():
        return results

    for test_dir in sorted(audited_dir.iterdir()):
        if not test_dir.is_dir():
            continue
        test_file = test_dir / "tests.py"
        if not test_file.exists():
            continue

        cn = test_dir.name

        # Use reference FDN card_impl.py from cards_dir
        ref_impl = cards_dir / "fdn" / cn / "card_impl.py"
        if not ref_impl.exists():
            results[cn] = CardResult(
                collector_number=cn,
                errors=[f"No reference card_impl.py at {ref_impl}"],
            )
            continue

        tmp_dir = tempfile.mkdtemp(prefix="eval_fdn_")
        try:
            tmp = Path(tmp_dir)
            shutil.copy2(ref_impl, tmp / "card_impl.py")
            shutil.copy2(test_file, tmp / "tests.py")
            test_utils_src = _REPO_ROOT / "benchmarks" / "sos" / "data" / "test_oracle_workspace" / "test_utils.py"
            if test_utils_src.exists():
                shutil.copy2(test_utils_src, tmp / "test_utils.py")

            pp = [str(tmp)]
            if engine_work.exists():
                pp.append(str(engine_work.parent))
            pp.append(str(_REPO_ROOT))

            passed, failed, total, errors = _run_pytest_with_pythonpath(
                tmp / "tests.py", pp, timeout=timeout,
            )
            results[cn] = _make_card_result(cn, passed, failed, total, errors)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    return results


def _eval_engine(
    engine_work: Path,
    engine_tests_dir: Path,
    timeout: int = 120,
    *,
    test_utils: Path | None = None,
) -> EngineResult:
    """Dimension 3: Engine Regression.

    Run the host-authoritative engine tests against the agent's engine_work/.
    When *test_utils* is given (the Contract Run path), the authoritative
    ``test_utils.py`` is staged ahead of the candidate engine on ``PYTHONPATH``
    so a candidate that tampered with its own ``test_utils`` cannot influence the
    engine regression score; a missing authoritative copy fails visibly.  Legacy
    callers pass ``None`` and keep the prior behavior.
    """
    if not engine_tests_dir.exists():
        return EngineResult(errors=[f"No engine tests at {engine_tests_dir}"])

    support_dir: str | None = None
    pp: list[str] = []
    if test_utils is not None:
        if not test_utils.is_file():
            return EngineResult(
                errors=[f"authoritative test_utils.py not found at {test_utils}"]
            )
        support_dir = tempfile.mkdtemp(prefix="eval_engine_support_")
        shutil.copy2(test_utils, Path(support_dir) / "test_utils.py")
        pp.append(support_dir)  # authoritative test_utils FIRST
    if engine_work.exists():
        pp.append(str(engine_work.parent))
    pp.append(str(_REPO_ROOT))

    try:
        passed, failed, total, errors = _run_pytest_with_pythonpath(
            engine_tests_dir, pp, timeout=timeout,
        )
    finally:
        if support_dir is not None:
            shutil.rmtree(support_dir, ignore_errors=True)
    return EngineResult(
        tests_passed=passed,
        tests_failed=failed,
        tests_total=total,
        pass_rate=passed / total if total > 0 else 0.0,
        errors=errors,
    )


# ---------------------------------------------------------------------------
# Benchmark-parameterized evaluation (Contract Run path)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EvalPaths:
    """The suites and support files the Audited Eval resolves per benchmark.

    ``target_set`` cards are what the agent implements (Dimension 1); ``fdn``
    is the FDN regression population (Dimension 2); ``engine_tests`` is the
    engine suite (Dimension 3).  All are resolved from the benchmark root so a
    new benchmark needs no code change — and the ``sos`` resolution reproduces
    the paths the legacy :func:`evaluate` hardcoded (see the resolution
    regression test).
    """

    benchmark_root: Path
    target_set: str
    cards_dir: Path
    engine_dir: Path
    audited_target: Path
    audited_fdn: Path
    engine_tests: Path
    test_utils: Path


def resolve_eval_paths(benchmark_root: Path, target_set: str) -> EvalPaths:
    """Resolve the Audited Eval paths for a benchmark rooted at *benchmark_root*.

    ``test_utils`` prefers the oracle workspace copy (as SOS uses today) and
    falls back to the staged workspace copy for benchmarks that ship only the
    latter (e.g. smoke).
    """
    benchmark_root = Path(benchmark_root)
    tests_audited = benchmark_root / "data" / "tests" / "audited"
    oracle_test_utils = benchmark_root / "data" / "test_oracle_workspace" / "test_utils.py"
    workspace_test_utils = benchmark_root / "workspace" / "test_utils.py"
    return EvalPaths(
        benchmark_root=benchmark_root,
        target_set=target_set,
        cards_dir=benchmark_root / "workspace" / "cards",
        engine_dir=benchmark_root / "workspace" / "engine",
        audited_target=tests_audited / target_set,
        audited_fdn=tests_audited / "fdn",
        engine_tests=benchmark_root / "workspace" / "engine_tests",
        test_utils=oracle_test_utils if oracle_test_utils.is_file() else workspace_test_utils,
    )


_GRADING_IGNORE = shutil.ignore_patterns("__pycache__", ".pytest_cache", ".git")


def _grade_audited_card(
    card_id: str,
    test_file: Path,
    overlay: Path,
    timeout: int,
    *,
    test_utils: Path | None,
) -> CardResult:
    """Grade one card's authoritative audited suite against the agent's tree.

    Grading isolation (BENCH-CONTRACT.md / #64): grading tests and grading
    support code are host-authoritative and candidate-immutable.  The audited
    ``tests.py`` and the *authoritative* ``test_utils.py`` are copied into an
    isolated temp dir that precedes the agent's *overlay* on ``PYTHONPATH``, so
    ``import test_utils`` always resolves to the host copy — a candidate that
    overwrites, deletes, or corrupts ``workspace/test_utils.py`` cannot influence
    the score — while the card's own ``cards.<set>.<card>.card_impl`` and
    ``engine`` still resolve from the tree the agent left behind (the evidence).
    A card-directory ``conftest.py`` is preserved as authoritative fixtures.
    Missing authoritative support fails visibly rather than scoring as zero.
    """
    if not test_file.exists():
        return CardResult(
            collector_number=card_id, skipped=True,
            errors=[f"No audited tests at {test_file}"],
        )
    if test_utils is None or not test_utils.is_file():
        return CardResult(
            collector_number=card_id, skipped=True,
            errors=[f"authoritative test_utils.py not found at {test_utils}"],
        )
    tmp_dir = tempfile.mkdtemp(prefix="eval_contract_")
    try:
        tmp = Path(tmp_dir)
        shutil.copy2(test_utils, tmp / "test_utils.py")
        card_conftest = test_file.parent / "conftest.py"
        if card_conftest.is_file():
            shutil.copy2(card_conftest, tmp / "conftest.py")
        shutil.copy2(test_file, tmp / "tests.py")
        # Grading support FIRST, candidate overlay SECOND: the authoritative
        # test_utils wins; candidate cards/engine still resolve from the overlay.
        pp = [str(tmp), str(overlay), str(_REPO_ROOT)]
        passed, failed, total, errors, test_nodes = _run_pytest_with_pythonpath(
            tmp / "tests.py", pp, timeout=timeout, capture_test_nodes=True,
        )
        cr = _make_card_result(card_id, passed, failed, total, errors)
        cr.test_nodes = test_nodes
        try:
            cr.tests_hash = hashlib.sha256(test_file.read_bytes()).hexdigest()
        except OSError:
            cr.tests_hash = ""
        return cr
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _target_card_id(target_set: str, collector_number: str, audited_target: Path) -> str:
    """Map a config collector number to its audited card-id directory name."""
    stripped = (
        f"{target_set}_{int(collector_number)}"
        if collector_number.isdigit() else f"{target_set}_{collector_number}"
    )
    raw = f"{target_set}_{collector_number}"
    if not (audited_target / stripped).is_dir() and (audited_target / raw).is_dir():
        return raw
    return stripped


def _eval_target_cards(
    overlay: Path,
    target_set: str,
    target_cards: list[str],
    audited_target: Path,
    timeout: int,
    *,
    test_utils: Path | None,
) -> dict[str, CardResult]:
    """Dimension 1: correctness of the benchmark's target cards."""
    results: dict[str, CardResult] = {}
    for cn in target_cards:
        card_id = _target_card_id(target_set, cn, audited_target)
        test_file = audited_target / card_id / "tests.py"
        results[card_id] = _grade_audited_card(
            card_id, test_file, overlay, timeout, test_utils=test_utils
        )
    return results


def _eval_audited_dir(
    overlay: Path,
    audited_dir: Path,
    timeout: int,
    *,
    test_utils: Path | None,
) -> dict[str, CardResult]:
    """Dimension 2: every card with an audited suite under *audited_dir* graded
    against the agent's tree (FDN regression)."""
    results: dict[str, CardResult] = {}
    if not audited_dir.is_dir():
        return results
    for card_dir in sorted(audited_dir.iterdir()):
        test_file = card_dir / "tests.py"
        if not card_dir.is_dir() or not test_file.exists():
            continue
        results[card_dir.name] = _grade_audited_card(
            card_dir.name, test_file, overlay, timeout, test_utils=test_utils,
        )
    return results


def evaluate_run(
    run_dir: Path,
    benchmark: BenchmarkRef,
    timeout: int = 60,
) -> FullEvalResult:
    """Run the three-dimension Audited Eval for a Contract Run.

    *benchmark* is a :class:`silverquillm.jobdir.BenchmarkRef` (duck-typed:
    ``root``, ``cards``, ``target_set``).  The agent's harvested tree at
    ``run_dir/workspace_final/`` is the evidence: every suite is resolved from
    the benchmark root and run against a throwaway copy of that tree, so
    ``cards``/``engine``/``test_utils`` resolve from what the agent left and the
    authoritative host-side suites do the grading.
    """
    run_dir = Path(run_dir)
    paths = resolve_eval_paths(benchmark.root, benchmark.target_set)
    result = FullEvalResult()

    agent_ws = run_dir / "workspace_final"
    if not agent_ws.is_dir():
        result.engine_result = EngineResult(
            errors=[f"no harvested workspace_final/ at {agent_ws}"]
        )
        result.compute_aggregates()
        return result

    overlay_root = tempfile.mkdtemp(prefix="eval_overlay_")
    overlay = Path(overlay_root) / "workspace"
    try:
        shutil.copytree(agent_ws, overlay, ignore=_GRADING_IGNORE)

        # Dimension 1 — target-card correctness.
        result.sos_results = _eval_target_cards(
            overlay, benchmark.target_set, list(benchmark.cards),
            paths.audited_target, timeout, test_utils=paths.test_utils,
        )
        # Dimension 2 — FDN card regression.
        result.fdn_results = _eval_audited_dir(
            overlay, paths.audited_fdn, timeout, test_utils=paths.test_utils,
        )
        # Dimension 3 — engine regression (authoritative suite + support, agent engine).
        result.engine_result = _eval_engine(
            overlay / "engine", paths.engine_tests, timeout=timeout,
            test_utils=paths.test_utils,
        )
    finally:
        shutil.rmtree(overlay_root, ignore_errors=True)

    result.compute_aggregates()
    return result


def evaluate(
    run_dir: Path,
    cards_dir: Path,
    engine_dir: Path,
    timeout: int = 60,
) -> FullEvalResult:
    """Run all three evaluation dimensions and return aggregated results.

    Parameters
    ----------
    run_dir:
        Path to the agent's run directory containing ``status.json``,
        ``cards/{cn}/card_impl.py``, and optionally ``engine_work/`` or
        ``engine_diff.patch``.
    cards_dir:
        Root of the cards directory (contains ``fdn/`` and ``sos/``
        subdirectories with reference card implementations).
    engine_dir:
        Path to the clean engine directory (used as base when applying
        ``engine_diff.patch``).
    timeout:
        Per-pytest-invocation timeout in seconds.

    Returns
    -------
    FullEvalResult
        Aggregated evaluation results across all three dimensions.
    """
    run_dir = Path(run_dir)
    cards_dir = Path(cards_dir)
    engine_dir = Path(engine_dir)

    result = FullEvalResult()

    # Prepare engine — returns (engine_path, staging_dir_to_cleanup).
    # On patch-apply failure we fall back to the baseline engine and record
    # the error so the run is visibly degraded rather than silently
    # mis-scored against the baseline. The error is merged into
    # ``result.engine_result.errors`` after Dimension 3 runs (since
    # ``_eval_engine`` builds a fresh ``EngineResult``).
    engine_prep_error: str | None = None
    try:
        engine_work, staging_dir = _prepare_engine_work(run_dir, engine_dir)
    except EnginePatchError as exc:
        engine_prep_error = str(exc)
        engine_work, staging_dir = engine_dir, None

    # Audited test directories — resolved from the SOS benchmark root (the
    # resolver reproduces the paths this function used to hardcode; a
    # regression test pins that equivalence).
    _sos_paths = resolve_eval_paths(_REPO_ROOT / "benchmarks" / "sos", "sos")
    audited_sos = _sos_paths.audited_target
    audited_fdn = _sos_paths.audited_fdn
    engine_tests = _sos_paths.engine_tests

    try:
        # Dimension 1: SOS Card Correctness
        result.sos_results = _eval_sos_cards(
            run_dir, cards_dir, engine_work, audited_sos, timeout=timeout,
        )

        # Dimension 2: FDN Card Regression
        result.fdn_results = _eval_fdn_cards(
            cards_dir, engine_work, audited_fdn, timeout=timeout,
        )

        # Dimension 3: Engine Regression
        result.engine_result = _eval_engine(
            engine_work, engine_tests, timeout=timeout,
        )
        if engine_prep_error is not None:
            result.engine_result.errors.insert(0, engine_prep_error)
    finally:
        # Clean up the engine staging directory if one was created
        if staging_dir is not None:
            shutil.rmtree(staging_dir, ignore_errors=True)

    # Compute aggregates
    result.compute_aggregates()

    return result
