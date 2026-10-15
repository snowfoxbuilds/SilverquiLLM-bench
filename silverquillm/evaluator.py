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

import ast
import configparser
import fnmatch
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from collections.abc import Collection, Iterable
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Protocol

from silverquillm import untrusted_git
from silverquillm.benchmark_targets import target_cards as resolve_target_cards


class GradedBenchmark(Protocol):
    """What grading reads from a benchmark (``silverquillm.karn.benchmark.Benchmark``)."""

    root: Path
    cards: list[str]
    target_set: str


logger = logging.getLogger(__name__)

# Repo root — resolved once at import time
_REPO_ROOT = Path(__file__).resolve().parent.parent
_BENCHMARK_DATA_ROOT: ContextVar[Path | None] = ContextVar("benchmark_data_root", default=None)
_PYTEST_ENVIRONMENT = (
    "PATH",
    "HOME",
    "TMPDIR",
    "LANG",
    "LC_ALL",
    "PYTHONDONTWRITEBYTECODE",
    "SILVERQUILLM_BENCH_ROOT",
)

__all__ = [
    "CardResult",
    "EnginePatchError",
    "EngineResult",
    "EvalPaths",
    "EvalResult",
    "FullEvalResult",
    "evaluate",
    "evaluate_run",
    "resolve_eval_paths",
    "run_audited_eval",
    "run_audited_eval_per_card",
    "run_cross_eval",
    "run_self_eval",
    "run_self_eval_flat",
    "run_tests",
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
    expected_test_functions: int | None = None
    not_run: list[dict] = field(default_factory=list)
    failure_messages: dict[str, str] = field(default_factory=dict)


@dataclass
class EngineResult:
    """Result of running core engine tests."""

    tests_passed: int = 0
    tests_failed: int = 0
    tests_total: int = 0
    pass_rate: float = 0.0
    errors: list[str] = field(default_factory=list)
    test_nodes: list[dict] = field(default_factory=list)
    expected_test_functions: int | None = None
    not_run: list[dict] = field(default_factory=list)
    failure_messages: dict[str, str] = field(default_factory=dict)


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
        if stripped.startswith(("FAILED ", "ERROR ")):
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
    if engine_work.is_dir() and not engine_work.is_symlink():
        # Copy engine_work into a staging dir named "engine/" so that
        # PYTHONPATH=staging_dir makes ``import engine as engine`` work.
        staging = Path(tempfile.mkdtemp(prefix="eval_engine_"))
        shutil.copytree(engine_work, staging / "engine", symlinks=True)
        return staging / "engine", staging

    snapshot_engine = run_dir / "workspace_final" / "engine"
    if snapshot_engine.is_dir() and not snapshot_engine.is_symlink():
        staging = Path(tempfile.mkdtemp(prefix="eval_engine_"))
        # The agent's links stay links; they resolve, if at all, inside the grader container.
        shutil.copytree(snapshot_engine, staging / "engine", symlinks=True)
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
            # The patch is candidate-derived: git reads no config beyond the host's overrides.
            subprocess.run(
                ["git", *untrusted_git.OVERRIDES, "apply", "-p1", str(patch_file)],
                check=True,
                capture_output=True,
                text=True,
                cwd=str(staging / "engine"),
                env=untrusted_git.environment(staging),
            )
        except subprocess.CalledProcessError as exc:
            shutil.rmtree(staging, ignore_errors=True)
            raise EnginePatchError(
                f"Failed to apply engine_diff.patch: {exc.stderr.strip()}"
            ) from exc
        return staging / "engine", staging

    # No engine modifications — use the original
    return engine_dir, None


# A failure message is a short diagnostic, never part of a score: candidate code shapes
# it, so it is bounded per node in characters and per evaluation in encoded bytes.
FAILURE_MESSAGE_LIMIT = 240
FAILURE_MESSAGE_BUDGET = 128 * 1024
NOT_RUN_REASONS = frozenset({
    "collection_error",        # the node's own test module failed to collect
    "import_error",            # ...because an import failed
    "collection_interrupted",  # another module's collection error stopped the session
    "timeout",                 # the suite hit its time limit
    "skipped",                 # skipped or xfail at run time
    "pytest_exited",           # pytest ended abnormally before reporting the node
    "not_reported",            # pytest finished without reporting the node
    "grading_support_missing",  # authoritative grading support was absent
    "candidate_code_missing",  # the candidate's engine or cards directory was absent
})  # fmt: skip
_DEFAULT_PYTHON_FILES = ("test_*.py", "tests.py")
# pytest's own exit statuses for a session that ran to its end: all passed, some failed,
# nothing collected.  Only a run without node reporting judges completion by them; with node
# reporting, the reporter's session-completion row decides, since candidate code can exit
# with any status before pytest finishes.
_PYTEST_ORDERLY_EXITS = (0, 1, 5)


def _generate_report_plugin(report_jsonl_path: str, session_token: str = "") -> str:
    """Return Python source for a pytest plugin that records test outcomes to JSONL.

    The generated plugin uses the ``pytest_runtest_logreport`` hook to capture
    per-test outcomes.  ``when == "call"`` reports give pass/fail, and a failure
    keeps a short message.  ``when == "setup"`` failures are also captured since
    those tests never reach ``call``, and ``when == "teardown"`` failures since
    they fail a node whose call passed.  Skipped and xfail outcomes, and collection
    errors, are recorded so that a node that did not run can say why; only pass
    and fail rows ever become ``test_nodes``.

    At session finish it writes one completion row carrying *session_token*, a
    per-run random value; a session cut short (``os._exit``, a crash) never
    reaches that hook, so the missing row marks the suite as ended early whatever
    exit status the process reported.  pytest also runs that hook after an
    interruption (``KeyboardInterrupt``, ``pytest.exit``) or an internal error, so
    the plugin withholds the row once ``pytest_keyboard_interrupt`` or
    ``pytest_internalerror`` has fired — except for pytest's own orderly stop
    after collection errors, which keeps its more specific diagnosis.

    The JSONL file path is baked into the source as a literal string so no
    env-var plumbing is needed.
    """
    # Escape backslashes and quotes in the path for embedding in Python source
    safe_path = report_jsonl_path.replace("\\", "\\\\").replace('"', '\\"')
    return f'''
import json as _json

_REPORT_PATH = "{safe_path}"
_SESSION_TOKEN = "{session_token}"
_LIMIT = {FAILURE_MESSAGE_LIMIT * 4}
_seen_nodes = set()
_collection_failed = False
_interrupted = False

def _message(report):
    text = None
    try:
        crash = getattr(report.longrepr, "reprcrash", None)
        if crash is not None:
            text = crash.message
    except Exception:
        text = None
    if not text:
        try:
            lines = [line for line in str(report.longrepr).splitlines() if line.strip()]
            text = lines[-1] if lines else ""
        except Exception:
            text = ""
    return str(text)[:_LIMIT]

def _write(row):
    with open(_REPORT_PATH, "a") as f:
        f.write(_json.dumps(row) + "\\n")

def pytest_runtest_logreport(report):
    """Record each test node outcome to a JSONL file."""
    nodeid = report.nodeid
    if report.when == "call":
        _seen_nodes.add(nodeid)
        # Skipped and xfail/xpass outcomes are never pass/fail outcomes.
        if report.skipped or hasattr(report, "wasxfail"):
            _write({{"nodeid": nodeid, "when": "call", "outcome": "skip"}})
            return
        row = {{"nodeid": nodeid, "when": "call", "outcome": "pass" if report.passed else "fail"}}
        if not report.passed:
            row["message"] = _message(report)
        _write(row)
    elif report.when == "setup" and (report.failed or report.skipped):
        # Setup failure or skip — the test never reaches "call"
        if nodeid not in _seen_nodes:
            _seen_nodes.add(nodeid)
            if report.failed:
                _write({{"nodeid": nodeid, "when": "setup", "outcome": "fail", "message": _message(report)}})
            else:
                _write({{"nodeid": nodeid, "when": "setup", "outcome": "skip"}})
    elif report.when == "teardown" and report.failed:
        # A teardown error fails a node whose call passed; the reader lets failure win.
        _write({{"nodeid": nodeid, "when": "teardown", "outcome": "fail", "message": _message(report)}})

def pytest_collectreport(report):
    """Record collection errors."""
    global _collection_failed
    if report.failed:
        _collection_failed = True
        nodeid = report.nodeid or "<collection-error>"
        _write({{"nodeid": nodeid, "when": "collect", "outcome": "fail", "message": _message(report)}})

def pytest_keyboard_interrupt(excinfo):
    """An interruption (KeyboardInterrupt, pytest.exit) means the session did not finish."""
    global _interrupted
    value = excinfo.value
    # pytest itself stops with Session.Interrupted after collection errors: an orderly end.
    if _collection_failed and type(value).__name__ == "Interrupted" and "during collection" in str(value):
        return
    _interrupted = True

def pytest_internalerror(excrepr, excinfo):
    """An internal error means the session did not finish."""
    global _interrupted
    _interrupted = True

def pytest_sessionfinish(session, exitstatus):
    """Record that the session ran to its end; never a test node."""
    if _interrupted:
        return
    _write({{"when": "session", "outcome": "complete", "token": _SESSION_TOKEN}})
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


def _suite_relative_nodeid(nodeid: str, suite_dir: str) -> str:
    """Make a node id relative to the graded suite root, keeping subdirectories."""
    if nodeid in ("", "<collection-error>", suite_dir):
        return "<collection-error>"
    return nodeid.removeprefix(suite_dir + "/")


def _bounded_message(value) -> str:
    """One printable line of at most ``FAILURE_MESSAGE_LIMIT`` characters, always valid UTF-8."""
    text = value[: FAILURE_MESSAGE_LIMIT * 4] if isinstance(value, str) else ""
    text = text.encode("utf-8", "replace").decode("utf-8")
    text = " ".join("".join(ch if ch.isprintable() else " " for ch in text).split())
    # Object addresses differ between gradings of the same workspace.
    text = re.sub(r"\b0x[0-9a-fA-F]{6,}\b", "0x…", text)
    return text[:FAILURE_MESSAGE_LIMIT]


@dataclass
class _Report:
    nodes: list[dict] = field(default_factory=list)
    skipped: set[str] = field(default_factory=set)
    messages: dict[str, str] = field(default_factory=dict)
    # Collector id (module, or class within it; ``""`` when pytest named none) -> message
    # of its collection error.
    collection_errors: dict[str, str] = field(default_factory=dict)
    # The reporter's session-completion row was read: pytest ran the session to its end.
    completed: bool = False


def _read_report(
    report_path: Path, suite_dir: str | None = None, session_token: str | None = None
) -> _Report:
    report = _Report()
    if not report_path.exists():
        return report

    seen: dict[str, int] = {}
    for line in report_path.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(entry, dict):
            continue
        if entry.get("when") == "session":
            # Completion only counts with this run's token; it is never a node.
            if session_token and entry.get("outcome") == "complete" and entry.get("token") == session_token:
                report.completed = True
            continue

        raw_nodeid = entry.get("nodeid", "")
        if not isinstance(raw_nodeid, str):
            continue
        outcome = entry.get("outcome")
        if suite_dir is not None:
            normalized = _suite_relative_nodeid(raw_nodeid, suite_dir)
        elif raw_nodeid and raw_nodeid != "<collection-error>":
            normalized = _normalize_nodeid(raw_nodeid)
        else:
            normalized = "tests.py::<collection-error>"

        if outcome == "skip":
            report.skipped.add(normalized)
            continue
        # Only accept the explicit values the conftest writes ('pass' / 'fail').
        # Any other or missing outcome is ignored — must not be silently coerced.
        if outcome not in ("pass", "fail"):
            continue
        collector = None
        if entry.get("when") == "collect":
            collector = normalized.removesuffix("::<collection-error>")
            collector = "" if collector == "<collection-error>" else collector
            if "::" in collector:
                # A class collector's row would read as a test node; mark it a collection error
                # so every scoring filter leaves it out, keeping its own id for reason matching.
                normalized = f"{collector}::<collection-error>"
        if outcome == "fail" and normalized not in report.messages:
            report.messages[normalized] = _bounded_message(entry.get("message"))
        if collector is not None:
            report.collection_errors.setdefault(collector, report.messages.get(normalized, ""))
        if normalized not in seen:
            seen[normalized] = len(report.nodes)
            report.nodes.append({"test_node": normalized, "outcome": outcome})
        elif outcome == "fail":
            # One node, several phases (call, then teardown): a failure in any phase fails it.
            report.nodes[seen[normalized]]["outcome"] = "fail"
    return report


def _parse_report_jsonl(report_path: Path, suite_dir: str | None = None) -> list[dict]:
    """Parse the JSONL report file into a list of ``{"test_node": ..., "outcome": ...}`` dicts.

    Deduplicates by nodeid (first occurrence wins).  Without *suite_dir*,
    normalizes nodeids to ``tests.py::test_x`` form and gives collection errors
    without a real nodeid a synthetic ``tests.py::<collection-error>`` id.  With
    *suite_dir*, nodeids are made relative to that suite directory and a
    nodeless collection error becomes ``<collection-error>``.
    """
    return _read_report(report_path, suite_dir).nodes


@dataclass
class _PytestRun:
    passed: int
    failed: int
    total: int
    errors: list[str]
    report: _Report
    timed_out: bool = False
    returncode: int | None = None
    # pytest did not run its session to the end (os._exit, a crash), whatever its exit status.
    ended_early: bool = False


def _run_pytest(
    test_path: Path,
    pythonpath_parts: list[str],
    timeout: int = 60,
    capture_test_nodes: bool = False,
    *,
    isolated_workspace: Path | None = None,
    suite_dir: str | None = None,
) -> _PytestRun:
    """Run pytest on *test_path* with a custom PYTHONPATH.

    Node capture loads a generated reporter as its own pytest plugin
    (``-p <module>``) from a fresh temporary directory placed first on
    ``PYTHONPATH``, under a per-call module name.  Pytest dispatches its hooks
    beside any ``conftest.py`` hooks, so authoritative support files are never
    edited and their own hooks keep running.  The directory, holding the plugin
    and its JSONL report, is removed however the run ends.
    """
    # Graded code gets no inherited credentials or tokens; see ADR-013.
    env = {key: os.environ[key] for key in _PYTEST_ENVIRONMENT if key in os.environ}
    data_root = _BENCHMARK_DATA_ROOT.get()
    if data_root is not None:
        env["SILVERQUILLM_BENCH_ROOT"] = str(data_root)
    existing = os.environ.get("PYTHONPATH", "") if isolated_workspace is None else ""
    parts = pythonpath_parts + ([existing] if existing else [])

    report_jsonl_path = None
    report_dir = None
    session_token = uuid.uuid4().hex

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        str(test_path),
        "--tb=short",
        "-q",
        "--no-header",
    ]

    if isolated_workspace is not None:
        cmd.extend([
            "-c", str(isolated_workspace / "pytest.ini"),
            "--confcutdir", str(isolated_workspace),
        ])

    if capture_test_nodes:
        report_dir = Path(tempfile.mkdtemp(prefix="eval_report_"))
        report_jsonl_path = report_dir / "report.jsonl"
        # First on the path, so no graded module can shadow the reporter.
        plugin = f"_silverquillm_node_report_{uuid.uuid4().hex}"
        (report_dir / f"{plugin}.py").write_text(
            _generate_report_plugin(str(report_jsonl_path), session_token)
        )
        parts = [str(report_dir), *parts]
        cmd.extend(["-p", plugin])
    env["PYTHONPATH"] = os.pathsep.join(parts)

    try:
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
                cwd=isolated_workspace,
                check=False,
            )
            combined = result.stdout + "\n" + result.stderr
        except subprocess.TimeoutExpired:
            # A timed-out suite grades nothing: no partial nodes are kept.
            return _PytestRun(0, 0, 0, [f"Timeout after {timeout}s"], _Report(), timed_out=True)

        passed, failed, total, errors = _parse_pytest_output(combined)
        report = (
            _read_report(report_jsonl_path, suite_dir, session_token)
            if report_jsonl_path
            else _Report()
        )
        if report_jsonl_path is not None:
            # A completion row never overrides an abnormal exit; pytest's orderly stop after
            # collection errors (status 2 with collection errors recorded) is not one.
            abnormal = result.returncode not in _PYTEST_ORDERLY_EXITS and not (
                result.returncode == 2 and report.collection_errors
            )
            ended_early = not report.completed or abnormal
        else:
            ended_early = result.returncode not in _PYTEST_ORDERLY_EXITS and all(
                error.startswith("FAILED ") for error in errors
            )
        if ended_early:
            # pytest did not finish its session (a crash, os._exit, an interruption or an
            # internal error): the grade must not look complete.
            errors.append(f"pytest_exited: exit status {result.returncode}")
        # test_nodes enumerates only executed pass/fail nodes.  Skipped and
        # xfail tests are intentionally omitted, so len(test_nodes) may be
        # less than tests_total when skips exist.  The authoritative counts
        # (tests_passed, tests_failed, tests_total) come from
        # _parse_pytest_output and are unaffected.
        return _PytestRun(
            passed, failed, total, errors, report,
            returncode=result.returncode, ended_early=ended_early,
        )
    finally:
        # However the body exits (normal return, TimeoutExpired, or any other
        # exception such as OSError/PermissionError).
        if report_dir is not None:
            shutil.rmtree(report_dir, ignore_errors=True)


def _run_pytest_with_pythonpath(
    test_path: Path,
    pythonpath_parts: list[str],
    timeout: int = 60,
    capture_test_nodes: bool = False,
    *,
    isolated_workspace: Path | None = None,
    suite_dir: str | None = None,
) -> tuple[int, int, int, list[str]] | tuple[int, int, int, list[str], list[dict]]:
    """Run pytest on *test_path* with a custom PYTHONPATH.

    Returns ``(passed, failed, total, errors)``.  When *capture_test_nodes*
    is ``True``, returns a 5-tuple with an additional list of per-node
    outcome dicts: ``[{"test_node": "tests.py::test_x", "outcome": "pass"|"fail"}, ...]``.
    """
    run = _run_pytest(
        test_path, pythonpath_parts, timeout, capture_test_nodes,
        isolated_workspace=isolated_workspace, suite_dir=suite_dir,
    )
    if capture_test_nodes:
        return run.passed, run.failed, run.total, run.errors, run.report.nodes
    return run.passed, run.failed, run.total, run.errors


# ---------------------------------------------------------------------------
# Expected test functions and the nodes that did not run
# ---------------------------------------------------------------------------


def _decorator_names(function: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    names = []
    for decorator in function.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        parts = []
        while isinstance(target, ast.Attribute):
            parts.append(target.attr)
            target = target.value
        if isinstance(target, ast.Name):
            parts.append(target.id)
        names.append(".".join(reversed(parts)))
    return names


def _is_test_function(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        and node.name.startswith("test")
        and not any(name.rsplit(".", 1)[-1] == "fixture" for name in _decorator_names(node))
    )


def _is_test_class(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.ClassDef)
        and node.name.startswith("Test")
        and not any(
            isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef) and item.name == "__init__"
            for item in node.body
        )
    )


def expected_test_functions(source: str, module_id: str) -> list[str] | None:
    """The test functions pytest collects from one authoritative test module, statically.

    Mirrors pytest's default discovery: module-level ``test*`` functions and the
    ``test*`` methods of ``Test*`` classes without ``__init__`` (nested ones too,
    and methods inherited from classes defined in the same module).  A
    parametrized function is one entry, without its ``[...]`` ids.  This reads
    host-side files only, never the candidate's code, so a candidate cannot
    change what is expected.  ``None`` when the module does not parse.
    """
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return None
    classes = {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}
    found: list[str] = []

    def methods(cls: ast.ClassDef, visiting: frozenset[str]) -> dict[str, None]:
        names: dict[str, None] = {}
        for base in cls.bases:
            if isinstance(base, ast.Name) and base.id in classes and base.id not in visiting:
                names.update(methods(classes[base.id], visiting | {base.id}))
        for item in cls.body:
            if _is_test_function(item):
                names[item.name] = None
        return names

    def visit_class(cls: ast.ClassDef, prefix: str, visiting: frozenset[str]) -> None:
        found.extend(f"{prefix}::{name}" for name in methods(cls, visiting))
        for item in cls.body:
            if _is_test_class(item):
                visit_class(item, f"{prefix}::{item.name}", visiting | {item.name})

    for node in tree.body:
        if _is_test_function(node):
            found.append(f"{module_id}::{node.name}")
        elif _is_test_class(node):
            visit_class(node, f"{module_id}::{node.name}", frozenset({node.name}))
    return list(dict.fromkeys(found))


def _python_files(support_dir: Path) -> tuple[str, ...]:
    """The suite's ``python_files``: the evaluator's own fallback ini when support has none."""
    ini = support_dir / "pytest.ini"
    if not ini.is_file():
        return _DEFAULT_PYTHON_FILES
    config = configparser.ConfigParser(interpolation=None)
    try:
        config.read(ini)
        value = config.get("pytest", "python_files", fallback="")
    except (configparser.Error, OSError, UnicodeDecodeError):
        value = ""
    return tuple(value.split()) or ("test_*.py", "*_test.py")


def expected_suite_functions(tests_dir: Path, python_files: Iterable[str]) -> list[str] | None:
    """Every expected test function of an authoritative suite directory, suite-relative."""
    patterns = tuple(python_files)
    found: list[str] = []
    for path in sorted(tests_dir.rglob("*.py")):
        relative = path.relative_to(tests_dir)
        if any(part.startswith(".") or part == "__pycache__" for part in relative.parts):
            continue
        if not any(fnmatch.fnmatch(path.name, pattern) for pattern in patterns):
            continue
        try:
            source = path.read_text()
        except (OSError, UnicodeDecodeError):
            return None
        functions = expected_test_functions(source, relative.as_posix())
        if functions is None:
            return None
        found.extend(functions)
    return found


def _base_node(test_node: str) -> str:
    return test_node.split("[", 1)[0]


def ran_functions(test_nodes: Iterable[dict]) -> set[str]:
    """The test functions with at least one reported node; worker and host share this rule."""
    return {
        _base_node(node["test_node"])
        for node in test_nodes
        if "::" in node["test_node"] and "<collection-error>" not in node["test_node"]
    }


def _not_run(expected: list[str] | None, run: _PytestRun | None, reason: str | None = None) -> list[dict]:
    """The expected test functions none of whose nodes ran, each with why.

    *reason* overrides the per-node diagnosis (used when the suite never started).
    """
    if not expected:
        return []
    if run is None:
        return [{"test_node": node, "reason": reason or "not_reported"} for node in expected]
    report = run.report
    ran = ran_functions(report.nodes)
    skipped = {_base_node(node) for node in report.skipped}
    missing = []
    for node in expected:
        if node in ran:
            continue
        # The most specific collection error covering the node: its class's, else its module's.
        covering = max(
            (key for key in report.collection_errors if key and (node == key or node.startswith(key + "::"))),
            key=len,
            default=None,
        )
        if reason is not None:
            why = reason
        elif run.timed_out:
            why = "timeout"
        elif node in skipped:
            why = "skipped"
        elif covering is not None or set(report.collection_errors) == {""}:
            message = report.collection_errors[covering if covering is not None else ""]
            why = (
                "import_error"
                if re.search(r"\b(ImportError|ModuleNotFoundError)\b", message or "")
                else "collection_error"
            )
        elif report.collection_errors:
            why = "collection_interrupted"
        elif run.ended_early:
            why = "pytest_exited"
        else:
            why = "not_reported"
        missing.append({"test_node": node, "reason": why})
    return missing


def _failure_messages(run: _PytestRun) -> dict[str, str]:
    failed = {node["test_node"] for node in run.report.nodes if node["outcome"] == "fail"}
    return {
        node: message
        for node, message in run.report.messages.items()
        if node in failed and message
    }


def failure_message_cost(node: str, message: str) -> int:
    """Bytes one ``node: message`` entry takes in the worker's ASCII-escaped JSON output.

    Counts the ``": "`` after the key and a ``", "`` separator, so the costs of a non-empty
    mapping's entries sum to exactly ``len(json.dumps(mapping))``: the two braces take the
    place of the one separator the last entry does not need.
    """
    return len(json.dumps(node)) + len(json.dumps(message)) + 4


def _apply_message_budget(result: FullEvalResult) -> None:
    """Drop failure messages past ``FAILURE_MESSAGE_BUDGET`` encoded bytes per evaluation."""
    remaining = FAILURE_MESSAGE_BUDGET
    holders = [
        *(result.sos_results[key] for key in sorted(result.sos_results)),
        *(result.fdn_results[key] for key in sorted(result.fdn_results)),
        result.engine_result,
    ]
    for holder in holders:
        kept = {}
        for node in sorted(holder.failure_messages):
            message = _bounded_message(holder.failure_messages[node])
            cost = failure_message_cost(node, message)
            if not message or cost > remaining:
                remaining = 0
                continue
            remaining -= cost
            kept[node] = message
        holder.failure_messages = kept


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
    support_dir: Path,
    test_utils: Path | None = None,
    cards_dir: Path | None = None,
    test_interface: Path | None = None,
) -> EngineResult:
    """Run authoritative engine tests beside isolated copies of the selected code.

    The workspace-relative card checks and repository-relative replay fixtures
    must see the same candidate packages as ordinary imports. Candidate pytest
    configuration and tests never enter the grading workspace: ``conftest.py``
    and ``pytest.ini`` come from the host-side *support_dir*. A benchmark with
    a Test Interface grades with its own *test_interface* and ``table.py``,
    both required, beside the candidate's ``test_utils.py``; one without
    grades with the authoritative ``test_utils.py`` (by default
    *support_dir*'s). Legacy engine-only staging supplies its reference cards
    explicitly.
    """
    if not engine_tests_dir.is_dir():
        return EngineResult(errors=[f"No engine tests at {engine_tests_dir}"])
    if not support_dir.is_dir():
        return EngineResult(errors=[f"authoritative engine support not found at {support_dir}"])
    # From the authoritative suite and its support pytest.ini, never the candidate's copy.
    expected = expected_suite_functions(engine_tests_dir, _python_files(support_dir))

    def unavailable(error: str, reason: str = "grading_support_missing") -> EngineResult:
        return EngineResult(
            errors=[error],
            expected_test_functions=None if expected is None else len(expected),
            not_run=_not_run(expected, None, reason),
        )

    if test_interface is not None:
        missing = interface_support_missing(test_interface)
        if missing is not None:
            return unavailable(missing)
        support = engine_work.parent / "test_utils.py"
    else:
        support = test_utils if test_utils is not None else support_dir / "test_utils.py"
        if not support.is_file():
            return unavailable(f"authoritative test_utils.py not found at {support}")
    selected_cards = cards_dir if cards_dir is not None else engine_work.parent / "cards"
    for source in (engine_work, selected_cards):
        if not source.is_dir():
            return unavailable(
                f"selected grading code directory not found at {source}", "candidate_code_missing"
            )

    data_root = _BENCHMARK_DATA_ROOT.get() or Path(
        os.environ.get("SILVERQUILLM_BENCH_ROOT", _REPO_ROOT)
    )
    with tempfile.TemporaryDirectory(prefix="eval_engine_") as directory:
        root = Path(directory)
        # Engine suites use parents[1] for workspace code and parents[4] for
        # replay fixtures. Preserve that topology without retaining host code.
        workspace = root / "benchmarks" / "selected" / "workspace"
        workspace.mkdir(parents=True)
        shutil.copytree(engine_work, workspace / "engine", ignore=_GRADING_IGNORE)
        shutil.copytree(selected_cards, workspace / "cards", ignore=_GRADING_IGNORE)
        # Suites import engine_tests.* whatever the source directory is called.
        staged_tests = workspace / "engine_tests"
        shutil.copytree(engine_tests_dir, staged_tests, ignore=_GRADING_IGNORE)
        if support.is_file():
            shutil.copy2(support, workspace / "test_utils.py")
        if test_interface is not None:
            _copy_interface(test_interface, workspace)
        for name in ("conftest.py", "pytest.ini"):
            source = support_dir / name
            if source.is_file():
                shutil.copy2(source, workspace / name)
        if not (workspace / "pytest.ini").is_file():
            (workspace / "pytest.ini").write_text(
                "[pytest]\npython_files = test_*.py tests.py\naddopts = --import-mode=importlib\n"
            )

        for relative in (
            "data/replays/golden",
            "data/replays/card_id_map.json",
            "data/replays/token_id_map.json",
            "scripts/triage_divergences.py",
        ):
            source, destination = data_root / relative, root / relative
            if source.is_dir():
                shutil.copytree(source, destination, ignore=_GRADING_IGNORE)
            elif source.is_file():
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)

        run = _run_pytest(
            staged_tests, [str(workspace), str(_REPO_ROOT)], timeout=timeout,
            capture_test_nodes=True, isolated_workspace=workspace,
            suite_dir=staged_tests.name,
        )
    return EngineResult(
        tests_passed=run.passed,
        tests_failed=run.failed,
        tests_total=run.total,
        pass_rate=run.passed / run.total if run.total > 0 else 0.0,
        errors=run.errors,
        test_nodes=run.report.nodes,
        expected_test_functions=None if expected is None else len(expected),
        not_run=_not_run(expected, run),
        failure_messages=_failure_messages(run),
    )


# ---------------------------------------------------------------------------
# Benchmark-parameterized evaluation (Contract Run path)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EvalPaths:
    """The suites and support files the Audited Eval resolves per benchmark.

    ``target_set`` cards are what the agent implements (Dimension 1); ``fdn``
    is the FDN regression population (Dimension 2); ``engine_tests`` is the
    engine suite (Dimension 3), and ``engine_support`` the host-side directory
    that supplies its ``conftest.py`` and ``pytest.ini``.  All are resolved
    from the benchmark root so a
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
    engine_support: Path
    test_interface: Path | None = None
    table: Path | None = None


def interface_table(test_interface: Path) -> Path:
    """The ``table.py`` beside *test_interface*: the benchmark's Audited Test
    helpers, which grading puts beside the Audited Tests with it. A benchmark
    with a Test Interface must ship it; this names where, present or not."""
    return test_interface.parent / "table.py"


def interface_support_missing(test_interface: Path) -> str | None:
    """Why the benchmark's Test Interface support cannot grade, or ``None``.

    Both ``test_interface.py`` and the ``table.py`` beside it are required:
    a candidate's copy of either must never stand in for a missing one.
    """
    for path in (test_interface, interface_table(test_interface)):
        if not path.is_file():
            return f"authoritative {path.name} not found at {path}"
    return None


def _copy_interface(test_interface: Path, destination: Path) -> None:
    """Copy the benchmark's Test Interface and its ``table.py`` into
    *destination*, ahead of anything the candidate staged."""
    shutil.copy2(test_interface, destination / "test_interface.py")
    shutil.copy2(interface_table(test_interface), destination / "table.py")


def resolve_eval_paths(benchmark_root: Path, target_set: str) -> EvalPaths:
    """Resolve the Audited Eval paths for a benchmark rooted at *benchmark_root*.

    ``test_utils`` prefers the oracle workspace copy (as SOS uses today) and
    falls back to the staged workspace copy for benchmarks that ship only the
    latter. ``test_interface`` is the benchmark's Test Interface, resolved the
    same way, or ``None`` for a benchmark that has none; a benchmark that has
    one grades with it and never with ``test_utils``. ``table`` is where the
    ``table.py`` it requires beside it must be, whether or not it is there.

    ``engine_tests`` is the hidden Audited Engine Tests directory
    ``data/tests/audited/engine`` whenever it exists, even empty; otherwise it
    falls back to the host copy of the staged ``workspace/engine_tests`` (as
    hob-medium and SOS grade). ``engine_support`` is always ``workspace``.
    """
    benchmark_root = Path(benchmark_root)
    tests_audited = benchmark_root / "data" / "tests" / "audited"
    oracle_test_utils = benchmark_root / "data" / "test_oracle_workspace" / "test_utils.py"
    workspace_test_utils = benchmark_root / "workspace" / "test_utils.py"
    test_interface = next(
        (
            path
            for path in (
                benchmark_root / "data" / "test_oracle_workspace" / "test_interface.py",
                benchmark_root / "workspace" / "test_interface.py",
            )
            if path.is_file()
        ),
        None,
    )
    audited_engine = tests_audited / "engine"
    return EvalPaths(
        benchmark_root=benchmark_root,
        target_set=target_set,
        cards_dir=benchmark_root / "workspace" / "cards",
        engine_dir=benchmark_root / "workspace" / "engine",
        audited_target=tests_audited / target_set,
        audited_fdn=tests_audited / "fdn",
        engine_tests=(
            audited_engine if audited_engine.is_dir()
            else benchmark_root / "workspace" / "engine_tests"
        ),
        test_utils=oracle_test_utils if oracle_test_utils.is_file() else workspace_test_utils,
        engine_support=benchmark_root / "workspace",
        test_interface=test_interface,
        table=interface_table(test_interface) if test_interface is not None else None,
    )


_GRADING_IGNORE = shutil.ignore_patterns("__pycache__", ".pytest_cache", ".git")


def _grade_audited_card(
    card_id: str,
    test_file: Path,
    overlay: Path,
    timeout: int,
    *,
    test_utils: Path | None,
    card_set: str | None = None,
    test_interface: Path | None = None,
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
    A benchmark with a Test Interface copies its *test_interface*, and the
    ``table.py`` it requires beside it, in the same way instead, and
    ``test_utils`` then resolves from the agent's tree.
    Missing authoritative support fails visibly rather than scoring as zero,
    and never falls back to the candidate's copy.
    """
    if not test_file.exists():
        return CardResult(
            collector_number=card_id, skipped=True,
            errors=[f"No audited tests at {test_file}"],
        )
    if test_interface:
        missing = interface_support_missing(test_interface)
    else:
        support = test_utils
        missing = (
            None if support is not None and support.is_file()
            else f"authoritative test_utils.py not found at {support}"
        )
    try:
        expected = expected_test_functions(test_file.read_text(), "tests.py")
    except (OSError, UnicodeDecodeError):
        expected = None
    if missing is not None:
        return CardResult(
            collector_number=card_id, skipped=True, errors=[missing],
            expected_test_functions=None if expected is None else len(expected),
            not_run=_not_run(expected, None, "grading_support_missing"),
        )
    tmp_dir = tempfile.mkdtemp(prefix="eval_contract_")
    try:
        tmp = Path(tmp_dir)
        if test_interface:
            _copy_interface(test_interface, tmp)
        else:
            shutil.copy2(support, tmp / "test_utils.py")
        card_conftest = test_file.parent / "conftest.py"
        if card_conftest.is_file():
            shutil.copy2(card_conftest, tmp / "conftest.py")
        shutil.copy2(test_file, tmp / "tests.py")
        # Grading support FIRST, candidate overlay SECOND: the authoritative
        # support wins; candidate cards/engine still resolve from the overlay.
        card_set = card_set or card_id.split("_", 1)[0]
        candidate_card = overlay / "cards" / card_set / card_id
        qualified = f"cards.{card_set}.{card_id}.card_impl"
        # Bind the file explicitly; a root card_impl or card-local engine must not change the grader's selection.
        (tmp / "card_impl.py").write_text(
            "import importlib as _importlib, importlib.util as _util, sys as _sys\n"
            "import engine as _engine, cards as _cards\n"
            + f"_sys.path.insert(1, {str(candidate_card)!r})\n"
            + f"_parent = _importlib.import_module({qualified.rpartition('.')[0]!r})\n"
            + f"_name = {qualified!r}\n"
            + f"_path = {str(candidate_card / 'card_impl.py')!r}\n"
            "_selected = _sys.modules.get(_name)\n"
            "if _selected is None or getattr(_selected, '__file__', None) != _path:\n"
            "    _spec = _util.spec_from_file_location(_name, _path)\n"
            "    _selected = _util.module_from_spec(_spec)\n"
            "    _sys.modules[_name] = _selected\n"
            "    _spec.loader.exec_module(_selected)\n"
            "_sys.modules[__name__] = _selected\n"
        )
        pp = [str(tmp), str(overlay), str(candidate_card), str(_REPO_ROOT)]
        run = _run_pytest(tmp / "tests.py", pp, timeout=timeout, capture_test_nodes=True)
        cr = _make_card_result(card_id, run.passed, run.failed, run.total, run.errors)
        cr.test_nodes = run.report.nodes
        cr.expected_test_functions = None if expected is None else len(expected)
        cr.not_run = _not_run(expected, run)
        cr.failure_messages = _failure_messages(run)
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


def fdn_target_card_ids(
    target_set: str, target_cards: Iterable[str], audited_root: Path
) -> frozenset[str]:
    """Target cards from the FDN set; their suites grade card correctness only."""
    return frozenset(
        _target_card_id("fdn", number, audited_root / "fdn")
        for card_set, number in resolve_target_cards(target_set, list(target_cards))
        if card_set == "fdn"
    )


def _eval_target_cards(
    overlay: Path,
    target_set: str,
    target_cards: list[str],
    audited_target: Path,
    timeout: int,
    *,
    test_utils: Path | None,
    test_interface: Path | None = None,
) -> dict[str, CardResult]:
    """Dimension 1: correctness of the benchmark's target cards."""
    results: dict[str, CardResult] = {}
    for card_set, cn in resolve_target_cards(target_set, target_cards):
        audited_set = audited_target.parent / card_set
        card_id = _target_card_id(card_set, cn, audited_set)
        test_file = audited_set / card_id / "tests.py"
        results[card_id] = _grade_audited_card(
            card_id, test_file, overlay, timeout, test_utils=test_utils, card_set=card_set,
            test_interface=test_interface,
        )
    return results


def _eval_audited_dir(
    overlay: Path,
    audited_dir: Path,
    timeout: int,
    *,
    test_utils: Path | None,
    exclude: Collection[str] = frozenset(),
    test_interface: Path | None = None,
) -> dict[str, CardResult]:
    """Dimension 2: every card with an audited suite under *audited_dir* graded
    against the agent's tree (FDN regression), except the cards in *exclude*."""
    results: dict[str, CardResult] = {}
    if not audited_dir.is_dir():
        return results
    for card_dir in sorted(audited_dir.iterdir()):
        test_file = card_dir / "tests.py"
        if not card_dir.is_dir() or not test_file.exists() or card_dir.name in exclude:
            continue
        results[card_dir.name] = _grade_audited_card(
            card_dir.name, test_file, overlay, timeout, test_utils=test_utils, card_set=audited_dir.name,
            test_interface=test_interface,
        )
    return results


def evaluate_run(
    run_dir: Path,
    benchmark: GradedBenchmark,
    timeout: int = 60,
    *,
    workspace_source: Path | None = None,
) -> FullEvalResult:
    """Run the three-dimension Audited Eval for a Contract Run.

    *benchmark* is any :class:`GradedBenchmark` (``root``, ``cards``,
    ``target_set``).  The agent's harvested tree at
    ``run_dir/workspace_final/`` is the evidence: every suite is resolved from
    the benchmark root and run against a throwaway copy of that tree, so
    ``cards``/``engine``/``test_utils`` resolve from what the agent left and the
    authoritative host-side suites do the grading.
    """
    run_dir = Path(run_dir)
    paths = resolve_eval_paths(benchmark.root, benchmark.target_set)
    result = FullEvalResult()

    agent_ws = Path(workspace_source) if workspace_source is not None else run_dir / "workspace_final"
    if not agent_ws.is_dir():
        result.engine_result = EngineResult(
            errors=[f"no harvested workspace_final/ at {agent_ws}"]
        )
        result.compute_aggregates()
        return result

    overlay_root = tempfile.mkdtemp(prefix="eval_overlay_")
    overlay = Path(overlay_root) / "workspace"
    data_root_token = _BENCHMARK_DATA_ROOT.set(benchmark.root.parent.parent.resolve())
    try:
        shutil.copytree(agent_ws, overlay, ignore=_GRADING_IGNORE)

        # Dimension 1 — target-card correctness.
        result.sos_results = _eval_target_cards(
            overlay, benchmark.target_set, list(benchmark.cards),
            paths.audited_target, timeout, test_utils=paths.test_utils,
            test_interface=paths.test_interface,
        )
        # Dimension 2 — FDN card regression.
        result.fdn_results = _eval_audited_dir(
            overlay, paths.audited_fdn, timeout, test_utils=paths.test_utils,
            test_interface=paths.test_interface,
            exclude=fdn_target_card_ids(
                benchmark.target_set, benchmark.cards, paths.audited_fdn.parent
            ),
        )
        # Dimension 3 — engine regression (authoritative suite + support, agent engine).
        result.engine_result = _eval_engine(
            overlay / "engine", paths.engine_tests, timeout=timeout,
            support_dir=paths.engine_support, test_utils=paths.test_utils,
            test_interface=paths.test_interface,
        )
    finally:
        shutil.rmtree(overlay_root, ignore_errors=True)
        _BENCHMARK_DATA_ROOT.reset(data_root_token)

    _apply_message_budget(result)
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
            support_dir=_sos_paths.engine_support, cards_dir=cards_dir,
        )
        if engine_prep_error is not None:
            result.engine_result.errors.insert(0, engine_prep_error)
    finally:
        # Clean up the engine staging directory if one was created
        if staging_dir is not None:
            shutil.rmtree(staging_dir, ignore_errors=True)

    _apply_message_budget(result)
    # Compute aggregates
    result.compute_aggregates()

    return result
