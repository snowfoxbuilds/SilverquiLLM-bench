"""Agent session manager for per-card benchmark runs.

Thin wrapper around :class:`~silverquillm.strategies.CardStrategy`:
set up workspace → delegate to ``CardStrategy.run_card()`` → harvest
files → log postmortem.

The agent invocation is delegated to an :class:`~silverquillm.adapters.AgentAdapter`
resolved from ``config.agent.adapter``.  The session itself is adapter-agnostic.

Public API:
- ``AgentSession`` — dataclass orchestrating a single card's benchmark run.
- ``BlindResult`` / ``TestInformedResult`` — legacy result dataclasses.
- Standalone helpers: ``setup_workspace``, ``run_blind``,
  ``run_test_informed``, ``cleanup``.
"""

from __future__ import annotations

import datetime
import difflib
import json
import logging
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from silverquillm.adapters import AgentAdapter, get_adapter
from silverquillm.config import BenchmarkConfig
from silverquillm.prompts import (
    blind_implementation_prompt,
    test_informed_prompt,
)
from silverquillm.template_gen import generate_template

logger = logging.getLogger(__name__)

__all__ = [
    "AgentSession",
    "BlindResult",
    "TestInformedResult",
    "_append_postmortem",
    "_generate_agent_thoughts",
    "append_raw_log",
    "init_run_engine",
    "commit_engine_changes",
    "compute_engine_diff",
    "save_engine_final",
    "snapshot_engine",
    "restore_engine_snapshot",
    "setup_workspace",
    "run_blind",
    "run_test_informed",
    "cleanup",
]

# Repo root — resolved once at import time
_REPO_ROOT = Path(__file__).resolve().parent.parent

# Directories that agents must never modify
_PROTECTED_DIRS: tuple[str, ...] = ("cards", "tests", "silverquillm", "benchmarks", "docs")


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class BlindResult:
    """Result of the blind (Step 1) implementation phase."""

    impl_path: Path | None
    tokens: int
    runtime_seconds: float
    peak_context: int
    status: str = "ok"


@dataclass
class TestInformedResult:
    """Result of the test-informed (Step 2) implementation phase."""

    impl_path: Path | None
    tests_path: Path | None
    iterations: int
    tokens: int
    runtime_seconds: float
    peak_context: int
    rules_lookups: int = 0
    status: str = "ok"


# ---------------------------------------------------------------------------
# Base-class extraction helper
# ---------------------------------------------------------------------------

_BASE_CLASS_NAMES = frozenset({
    "GameObject",
    "CardImpl",
    "Creature",
    "Instant",
    "Sorcery",
    "Enchantment",
    "Aura",
    "Artifact",
    "ArtifactCreature",
    "Planeswalker",
    "Land",
})

_SUPPORTING_DATACLASSES = frozenset({
    "ActivatedAbility",
    "LoyaltyAbility",
    "ManaAbility",
    "ContinuousEffect",
    "Mode",
})


def _extract_base_classes(card_py_path: Path) -> str:
    """Extract CardImpl and subclass definitions from engine/card.py.

    Returns a self-contained Python source string with the class hierarchy
    that agents need to subclass.
    """
    source = card_py_path.read_text()
    return source


# ---------------------------------------------------------------------------
# AgentSession dataclass
# ---------------------------------------------------------------------------


@dataclass
class AgentSession:
    """Manage a single card's agent session with contamination controls.

    Fields
    ------
    config:
        Benchmark run configuration.
    card_spec:
        Card specification dictionary (as produced by ``card_spec.py``).
    card_dir:
        Path to the per-card directory containing ``card_spec.json``.
    """

    config: BenchmarkConfig
    card_spec: dict[str, Any]
    card_dir: str
    run_engine_dir: Path | None = field(default=None)
    run_dir: Path | None = field(default=None)
    _workspace: Path | None = field(default=None, init=False, repr=False)
    _adapter: AgentAdapter | None = field(default=None, init=False, repr=False)

    # -- Convenience properties matching TODO contract names ----------------

    @property
    def card_name(self) -> str:
        """Card name derived from the spec."""
        return self.card_spec.get("name", "")

    @property
    def workspace(self) -> Path | None:
        """Current workspace path (None before setup)."""
        return self._workspace

    # ------------------------------------------------------------------
    # Workspace setup
    # ------------------------------------------------------------------

    def setup_workspace(self) -> Path:
        """Create a fresh temporary workspace directory.

        Copies the following into the workspace:
        - ``card_spec.json`` from *card_dir*
        - ``engine_api.md`` from ``docs/``
        - ``base_classes.py`` extracted from ``engine/card.py``
        - ``template.py`` generated for this card
        - ``rules_overview.md`` from ``benchmarks/sos/data/``
        - ``foundations/`` read-only copy from ``cards/foundations/``

        Returns
        -------
        Path
            The workspace directory path.
        """
        workspace = _REPO_ROOT / ".workspace"
        # Clean slate for each card — remove any leftover from a previous run
        if workspace.exists():
            for root, dirs, files in os.walk(workspace):
                for dname in dirs:
                    try:
                        (Path(root) / dname).chmod(0o755)
                    except OSError:
                        pass
                for fname in files:
                    try:
                        (Path(root) / fname).chmod(0o644)
                    except OSError:
                        pass
            shutil.rmtree(workspace)
        workspace.mkdir(parents=True)
        self._workspace = workspace

        repo_root = _REPO_ROOT

        # 1. card_spec.json
        card_spec_src = Path(self.card_dir) / "card_spec.json"
        if card_spec_src.exists():
            shutil.copy2(card_spec_src, workspace / "card_spec.json")
        else:
            # Write from in-memory spec
            (workspace / "card_spec.json").write_text(
                json.dumps(self.card_spec, indent=2)
            )

        # 2. engine_api.md
        engine_api_src = repo_root / "docs" / "engine_api.md"
        if engine_api_src.exists():
            shutil.copy2(engine_api_src, workspace / "engine_api.md")

        # 3. base_classes.py — extracted from engine/card.py
        card_py = (
            self.run_engine_dir / "card.py"
            if self.run_engine_dir and (self.run_engine_dir / "card.py").exists()
            else repo_root / "engine" / "card.py"
        )
        if card_py.exists():
            base_classes_content = _extract_base_classes(card_py)
            (workspace / "base_classes.py").write_text(base_classes_content)

        # 4. template.py — generated for this card
        template_source = generate_template(self.card_spec)
        (workspace / "template.py").write_text(template_source)

        # Also write as card_impl.py — the canonical implementation file.
        # The agent is instructed to edit card_impl.py directly.
        (workspace / "card_impl.py").write_text(template_source)

        # 5. rules_overview.md
        rules_src = repo_root / "benchmarks" / "sos" / "data" / "rules_overview.md"
        if rules_src.exists():
            shutil.copy2(rules_src, workspace / "rules_overview.md")

        # 6. engine/ — writable copy (from run_engine_dir if available, else repo)
        engine_src = (
            self.run_engine_dir
            if self.run_engine_dir and self.run_engine_dir.exists()
            else repo_root / "engine"
        )
        if engine_src.exists():
            engine_dst = workspace / "engine"
            shutil.copytree(engine_src, engine_dst)

        # 7. foundations/ — read-only copy
        foundations_src = repo_root / "cards" / "foundations"
        if foundations_src.exists():
            foundations_dst = workspace / "foundations"
            shutil.copytree(foundations_src, foundations_dst)
            # Make read-only
            for root, dirs, files in os.walk(foundations_dst):
                for fname in files:
                    fpath = Path(root) / fname
                    fpath.chmod(0o444)
                for dname in dirs:
                    dpath = Path(root) / dname
                    dpath.chmod(0o555)
            foundations_dst.chmod(0o555)
        

        # Copy test_utils files so agent can import/read them (impl_test mode only)
        if self.config.mode != "blind":
            test_utils_py = repo_root / "tests" / "test_utils.py"
            if test_utils_py.exists():
                shutil.copy2(test_utils_py, workspace / "test_utils.py")
            test_utils_md = repo_root / "docs" / "test_utils.md"
            if test_utils_md.exists():
                shutil.copy2(test_utils_md, workspace / "test_utils.md")

        logger.info("Workspace created at %s", workspace)

        # Init a git repo in the directory so that agents don't try to go to the root
        subprocess.run(["git", "init"], cwd=str(workspace), capture_output=True)

        # Initialize and set up the adapter
        adapter = self._get_adapter()
        adapter.setup()

        return workspace

    # ------------------------------------------------------------------
    # Agent adapter lifecycle
    # ------------------------------------------------------------------

    def _get_adapter(self) -> AgentAdapter:
        """Return the adapter instance, creating it lazily if needed."""
        if self._adapter is None:
            self._adapter = get_adapter(self.config)
        return self._adapter

    # ------------------------------------------------------------------
    # Agent invocation (adapter-based)
    # ------------------------------------------------------------------

    def _run_agent(self, prompt: str, workspace: Path) -> str:
        """Run an agent session with the given prompt via the configured adapter.

        This method delegates to the :class:`AgentAdapter` resolved from
        ``config.agent.adapter``.  It can be monkey-patched or overridden
        in tests to avoid actual subprocess calls.

        Parameters
        ----------
        prompt:
            The full prompt text to send to the agent.
        workspace:
            Working directory for the agent.

        Returns
        -------
        str
            Raw output from the agent.

        Raises
        ------
        subprocess.TimeoutExpired
            When the process exceeds timeout_per_card seconds.
        """
        adapter = self._get_adapter()
        logger.debug(
            "Invoking adapter with timeout=%s",
            self.config.agent.timeout_per_card,
        )
        return adapter.run(prompt, workspace)

    # Result harvesting
    # ------------------------------------------------------------------

    def harvest_results(self, card_results_dir: Path) -> None:
        """Copy agent-produced files from workspace to the card results directory.

        Must be called BEFORE cleanup() destroys the workspace.
        """
        if not self._workspace or not self._workspace.exists():
            return
        card_results_dir.mkdir(parents=True, exist_ok=True)
        for filename in ("card_impl.py", "tests.py"):
            src = self._workspace / filename
            if src.exists():
                shutil.copy2(src, card_results_dir / filename)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # High-level strategy-based card execution
    # ------------------------------------------------------------------

    def run_card(self) -> "CardRunResult":
        """Execute the card using the strategy selected by ``config.mode``.

        Delegates to :meth:`CardStrategy.run_card` after setting up the
        workspace (if not already done).  Wraps the strategy call with:
        - Protected-path snapshot & violation checking
        - Postmortem logging and raw output
        - ``agent_thoughts.md`` generation

        Returns
        -------
        CardRunResult
        """
        from silverquillm.strategies import CardRunResult, CardRunStatus, get_strategy  # noqa: F811

        if self._workspace is None:
            self.setup_workspace()

        strategy = get_strategy(self.config.mode)
        adapter = self._get_adapter()
        timeout = self.config.agent.timeout_per_card

        # Snapshot protected paths before strategy execution
        protected_snapshot = _snapshot_all_protected(_REPO_ROOT)

        # Snapshot engine directory before card execution
        engine_snapshot_dir: Path | None = None
        if self.run_engine_dir and self.run_engine_dir.exists():
            engine_snapshot_dir = snapshot_engine(self.run_engine_dir)

        start = time.monotonic()

        postmortem_path = _get_postmortem_path(self.run_dir, self.card_name)
        raw_log_path = _get_raw_log_path(self.run_dir)

        try:
            result = strategy.run_card(
                card_spec=self.card_spec,
                workspace=self._workspace,
                adapter=adapter,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            elapsed = time.monotonic() - start
            # Restore engine from snapshot on timeout
            if engine_snapshot_dir and self.run_engine_dir:
                restore_engine_snapshot(self.run_engine_dir, engine_snapshot_dir)
            if postmortem_path:
                _append_postmortem(
                    postmortem_path=postmortem_path,
                    prompt="(strategy-level)",
                    response="TimeoutExpired",
                    tokens=None,
                    timing_ms=elapsed * 1000,
                    round_num=1,
                    status="error",
                )
            if raw_log_path:
                append_raw_log(raw_log_path, self.card_name, self.config.mode, 1, "(strategy-level)", "TimeoutExpired")
            return CardRunResult(
                status=CardRunStatus.timeout,
                runtime_ms=int(elapsed * 1000),
            )
        except Exception as exc:
            elapsed = time.monotonic() - start
            # Restore engine from snapshot on unexpected errors
            if engine_snapshot_dir and self.run_engine_dir:
                restore_engine_snapshot(self.run_engine_dir, engine_snapshot_dir)
            response_text = f"{type(exc).__name__}: {exc}"
            if postmortem_path:
                _append_postmortem(
                    postmortem_path=postmortem_path,
                    prompt="(strategy-level)",
                    response=response_text,
                    tokens=None,
                    timing_ms=elapsed * 1000,
                    round_num=1,
                    status="error",
                )
            if raw_log_path:
                append_raw_log(raw_log_path, self.card_name, self.config.mode, 1, "(strategy-level)", response_text)
            raise

        elapsed = time.monotonic() - start

        # If the strategy returned a timeout result (production adapters catch
        # timeouts internally and return CardRunResult(status=timeout) instead
        # of raising subprocess.TimeoutExpired), restore the engine snapshot so
        # corrupted partial engine modifications cannot poison subsequent cards.
        if result.status == CardRunStatus.timeout:
            if engine_snapshot_dir and self.run_engine_dir:
                restore_engine_snapshot(self.run_engine_dir, engine_snapshot_dir)
        elif engine_snapshot_dir and engine_snapshot_dir.exists():
            # Strategy succeeded — delete the engine snapshot
            shutil.rmtree(engine_snapshot_dir)

        # Log successful strategy execution
        if postmortem_path:
            _append_postmortem(
                postmortem_path=postmortem_path,
                prompt="(strategy-level)",
                response=f"status={result.status.value}",
                tokens=None,
                timing_ms=elapsed * 1000,
                round_num=1,
                status="success",
            )
        if raw_log_path:
            append_raw_log(
                raw_log_path, self.card_name, self.config.mode, 1,
                "(strategy-level)", f"status={result.status.value}",
            )

        # Check for violations (agent modifying protected paths)
        violations = _check_violations(
            self._workspace,
            before=protected_snapshot,
            output_dir=Path(self.config.output_dir) if self.config.output_dir else None,
        )
        if violations:
            logger.warning("Violations detected during card run: %s", violations)
            result = CardRunResult(
                status=CardRunStatus.no_output,
                files_written=result.files_written,
                runtime_ms=int(elapsed * 1000),
                engine_modified=result.engine_modified,
                violations=violations,
            )

        # Generate agent_thoughts.md
        if self.run_dir:
            try:
                _generate_agent_thoughts(self.run_dir, self.card_name)
            except Exception:
                logger.debug(
                    "Failed to generate agent_thoughts.md for %s",
                    self.card_name,
                    exc_info=True,
                )

        return result

    def cleanup(self) -> None:
        """Remove the temporary workspace directory and tear down the adapter."""
        # Tear down the adapter first
        if self._adapter is not None:
            try:
                self._adapter.teardown()
            except Exception:  # noqa: BLE001
                logger.warning("Adapter teardown failed", exc_info=True)
            self._adapter = None

        if self._workspace and self._workspace.exists():
            # Restore write permissions before removal
            for root, dirs, files in os.walk(self._workspace):
                for dname in dirs:
                    dpath = Path(root) / dname
                    dpath.chmod(0o755)
                for fname in files:
                    fpath = Path(root) / fname
                    fpath.chmod(0o644)
            shutil.rmtree(self._workspace, ignore_errors=True)
            self._workspace = None


# ---------------------------------------------------------------------------
# Postmortem JSONL logging
# ---------------------------------------------------------------------------

_POSTMORTEM_RESPONSE_MAX = 10_000


def _append_postmortem(
    postmortem_path: Path,
    prompt: str,
    response: str,
    tokens: int | None,
    timing_ms: float,
    round_num: int,
    status: str,
    *,
    tests_passing: bool | None = None,
) -> None:
    """Append a single JSON line to the postmortem log file.

    Parameters
    ----------
    postmortem_path:
        Path to the ``postmortem.jsonl`` file.
    prompt:
        The prompt text sent to the agent.
    response:
        The agent's response text.  Truncated to *_POSTMORTEM_RESPONSE_MAX*
        characters when writing.
    tokens:
        Estimated token count, or ``None`` if unavailable.
    timing_ms:
        Duration of the invocation in milliseconds.
    round_num:
        1-based round number (1 for blind phase).
    status:
        ``"success"`` or ``"error"``.
    tests_passing:
        Whether pytest passed after this round.  ``None`` when unknown
        (e.g. blind phase or timeout before tests ran).
    """
    # Truncate very long responses
    if len(response) > _POSTMORTEM_RESPONSE_MAX:
        response = response[:_POSTMORTEM_RESPONSE_MAX] + "...[truncated]"

    entry: dict[str, Any] = {
        "prompt": prompt,
        "response": response,
        "tokens": tokens,
        "timing_ms": timing_ms,
        "round": round_num,
        "status": status,
    }
    if tests_passing is not None:
        entry["tests_passing"] = tests_passing

    postmortem_path.parent.mkdir(parents=True, exist_ok=True)
    with postmortem_path.open("a") as f:
        f.write(json.dumps(entry) + "\n")


def _get_postmortem_path(run_dir: Path | None, card_name: str) -> Path | None:
    """Return the postmortem.jsonl path, or None if run_dir is not set."""
    if not run_dir:
        return None
    return run_dir / "cards" / card_name / "postmortem.jsonl"


def _get_raw_log_path(run_dir: Path | None) -> Path | None:
    """Return the run-level raw_agent_log.jsonl path, or None if run_dir is not set."""
    if not run_dir:
        return None
    return run_dir / "raw_agent_log.jsonl"


def append_raw_log(
    run_log_path: Path,
    card_name: str,
    phase: str,
    round_num: int,
    prompt: str,
    response: str,
) -> None:
    """Append a JSON line to the run-level raw agent log.

    Unlike postmortem.jsonl, responses are never truncated — this is the
    authoritative full-output record for the entire run.
    """
    entry: dict[str, Any] = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "card_name": card_name,
        "phase": phase,
        "round": round_num,
        "prompt": prompt,
        "response": response,
    }
    run_log_path.parent.mkdir(parents=True, exist_ok=True)
    with run_log_path.open("a") as f:
        f.write(json.dumps(entry) + "\n")


# ---------------------------------------------------------------------------
# Agent thoughts narrative generation
# ---------------------------------------------------------------------------


def _generate_agent_thoughts(output_dir: str | Path, card_name: str) -> Path | None:
    """Generate ``agent_thoughts.md`` summarising reasoning across rounds.

    Reads ``<output_dir>/<card_name>/postmortem.jsonl`` and produces a
    structured Markdown narrative at
    ``<output_dir>/<card_name>/agent_thoughts.md``.

    Parameters
    ----------
    output_dir:
        Top-level output directory for the benchmark run.
    card_name:
        Name of the card whose postmortem should be summarised.

    Returns
    -------
    Path | None
        Path to the generated file, or ``None`` if the postmortem file
        does not exist or is empty.
    """
    output_dir = Path(output_dir)
    postmortem_path = output_dir / "cards" / card_name / "postmortem.jsonl"

    if not postmortem_path.exists():
        return None

    entries: list[dict[str, Any]] = []
    for line in postmortem_path.read_text().splitlines():
        line = line.strip()
        if line:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    if not entries:
        return None

    # --- Determine overall status ---
    statuses = [e.get("status", "unknown") for e in entries]
    total_rounds = len(entries)
    success_count = statuses.count("success")
    error_count = total_rounds - success_count

    # Check if any entry carries test-pass/fail information.  When present,
    # use the *last* entry's ``tests_passing`` flag to decide whether tests
    # actually passed — adapter call "success" only means the adapter ran
    # without error, not that pytest passed.
    tests_passing_values = [e.get("tests_passing") for e in entries if "tests_passing" in e]
    final_tests_passing = tests_passing_values[-1] if tests_passing_values else None

    if error_count == 0:
        # All adapter calls succeeded, but if tests never passed we should
        # not claim "all_passed".
        if final_tests_passing is False:
            overall_status = "max_rounds_exhausted"
        else:
            overall_status = "all_passed"
    elif success_count == 0:
        overall_status = "all_failed"
    else:
        overall_status = "partial"

    lines: list[str] = []

    # --- Header ---
    lines.append(f"# Agent Thoughts: {card_name}")
    lines.append("")
    lines.append(f"**Total rounds:** {total_rounds}  ")
    lines.append(f"**Overall status:** {overall_status}  ")
    lines.append("")

    # --- Per-round sections ---
    lines.append("## Round Details")
    lines.append("")

    for entry in entries:
        round_num = entry.get("round", "?")
        status = entry.get("status", "unknown")
        timing_ms = entry.get("timing_ms", 0)
        prompt = entry.get("prompt", "")
        response = entry.get("response", "")

        prompt_summary = prompt[:100]
        if len(prompt) > 100:
            prompt_summary += "..."

        response_summary = response[:200]
        if len(response) > 200:
            response_summary += "..."

        timing_s = timing_ms / 1000.0

        lines.append(f"### Round {round_num}")
        lines.append("")
        lines.append(f"- **Status:** {status}")
        lines.append(f"- **Timing:** {timing_s:.2f}s")
        lines.append(f"- **Prompt (first 100 chars):** {prompt_summary}")
        lines.append(f"- **Response (first 200 chars):** {response_summary}")
        lines.append("")

    # --- Final analysis ---
    lines.append("## Analysis")
    lines.append("")

    if total_rounds == 1:
        lines.append(f"Single round executed with status: {statuses[0]}.")
    else:
        # Detect patterns
        patterns: list[str] = []

        if overall_status == "all_passed":
            patterns.append(
                f"All {total_rounds} rounds completed successfully."
            )
        elif overall_status == "max_rounds_exhausted":
            patterns.append(
                f"All {total_rounds} adapter calls succeeded but tests "
                f"never passed — rounds exhausted."
            )
        elif overall_status == "all_failed":
            patterns.append(
                f"All {total_rounds} rounds failed — persistent errors throughout."
            )
        else:
            patterns.append(
                f"{success_count}/{total_rounds} rounds succeeded, "
                f"{error_count} failed."
            )

        # Check for improvement (errors early, success later)
        if len(statuses) >= 2:
            if statuses[0] == "error" and statuses[-1] == "success":
                patterns.append("Improvement observed: early failures resolved in later rounds.")
            elif statuses[0] == "success" and statuses[-1] == "error":
                patterns.append("Regression observed: initial success followed by later failures.")

        # Check for persistent failures
        if error_count > 1:
            patterns.append(f"Persistent failures detected across {error_count} rounds.")

        for p in patterns:
            lines.append(f"- {p}")

    lines.append("")

    # --- Write the file ---
    thoughts_path = output_dir / "cards" / card_name / "agent_thoughts.md"
    thoughts_path.parent.mkdir(parents=True, exist_ok=True)
    thoughts_path.write_text("\n".join(lines))

    return thoughts_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token."""
    return len(text) // 4


def _count_rules_lookups(output: str) -> int:
    """Count references to rules lookups in agent output."""
    # Pattern matches lines like "Looking up rule 702.3" or "rules_lookup"
    return len(re.findall(r"(?:rules?_?lookup|looking up rule)", output, re.IGNORECASE))


def _snapshot_mtimes(root: Path) -> dict[Path, float]:
    """Record mtime for every file under *root*."""
    snapshot: dict[Path, float] = {}
    for dirpath, _dirs, files in os.walk(root):
        for fname in files:
            fpath = Path(dirpath) / fname
            try:
                snapshot[fpath] = fpath.stat().st_mtime
            except OSError:
                pass
    return snapshot


def _snapshot_all_protected(repo_root: Path) -> dict[Path, float]:
    """Snapshot mtimes for all protected directories that exist under *repo_root*."""
    merged: dict[Path, float] = {}
    for dirname in _PROTECTED_DIRS:
        dirpath = repo_root / dirname
        if dirpath.is_dir():
            merged.update(_snapshot_mtimes(dirpath))
    return merged


def _check_violations(workspace: Path, before: dict[Path, float] | None = None, output_dir: Path | None = None) -> list[str]:
    """Return list of violation descriptions for files outside *workspace* that changed.

    Compares current mtimes against the *before* snapshot.  If no snapshot is
    provided, the check cannot detect violations and returns an empty list.
    Files under *output_dir* are excluded — the runner itself writes legitimate
    log files there and those are not agent contamination.
    """
    if before is None:
        return []
    after = _snapshot_all_protected(_REPO_ROOT)
    violations: list[str] = []
    workspace_resolved = workspace.resolve()
    output_resolved = output_dir.resolve() if output_dir else None
    for path, mtime in after.items():
        # Skip __pycache__ — Python auto-generates these on import
        if "__pycache__" in path.parts:
            continue
        # Files inside the workspace are expected to change
        try:
            if path.resolve().is_relative_to(workspace_resolved):
                continue
            if output_resolved and path.resolve().is_relative_to(output_resolved):
                continue
        except (OSError, ValueError):
            pass
        prior = before.get(path)
        if prior is None:
            # Newly created file
            desc = f"{path} was created"
            logger.warning("Contamination violation: %s", desc)
            violations.append(desc)
        elif mtime > prior:
            # Modified file
            desc = f"{path} was modified"
            logger.warning("Contamination violation: %s", desc)
            violations.append(desc)
    # Check for deletions: files in before but missing from after
    for path in before:
        if path in after:
            continue
        # Skip __pycache__ — Python auto-generates these on import
        if "__pycache__" in path.parts:
            continue
        try:
            if path.resolve().is_relative_to(workspace_resolved):
                continue
            if output_resolved and path.resolve().is_relative_to(output_resolved):
                continue
        except (OSError, ValueError):
            pass
        desc = f"{path} was deleted"
        logger.warning("Contamination violation: %s", desc)
        violations.append(desc)
    return violations


# ---------------------------------------------------------------------------
# Persistent run-level engine helpers
# ---------------------------------------------------------------------------


def init_run_engine(output_dir: str | Path) -> Path:
    """Create a persistent run-level engine directory.

    Copies the repo's ``engine/`` tree into ``<output_dir>/run_engine/``
    so that it can be shared (and evolved) across all cards in the run.

    Parameters
    ----------
    output_dir:
        Top-level output directory for the benchmark run.

    Returns
    -------
    Path
        Path to the newly created run-level engine directory.
    """
    output_dir = Path(output_dir)
    run_engine = output_dir / "run_engine"
    engine_src = _REPO_ROOT / "engine"
    if engine_src.exists():
        if run_engine.exists():
            shutil.rmtree(run_engine)
        shutil.copytree(engine_src, run_engine)
    else:
        run_engine.mkdir(parents=True, exist_ok=True)
    return run_engine


def snapshot_engine(run_engine_dir: Path) -> Path:
    """Create a snapshot of the run-level engine directory.

    Copies *run_engine_dir* to ``<run_engine_dir>.snapshot`` so it can be
    restored if a card run fails or times out.

    Parameters
    ----------
    run_engine_dir:
        The persistent run-level engine directory.

    Returns
    -------
    Path
        Path to the snapshot directory.
    """
    snapshot_dir = run_engine_dir.with_suffix(".snapshot")
    if snapshot_dir.exists():
        shutil.rmtree(snapshot_dir)
    shutil.copytree(run_engine_dir, snapshot_dir)
    return snapshot_dir


def restore_engine_snapshot(run_engine_dir: Path, snapshot_dir: Path) -> None:
    """Restore the run-level engine directory from a snapshot.

    Replaces *run_engine_dir* with the contents of *snapshot_dir*,
    effectively rolling back any partial modifications made during a
    failed card run.

    Parameters
    ----------
    run_engine_dir:
        The persistent run-level engine directory to restore.
    snapshot_dir:
        The snapshot directory to restore from.
    """
    if not snapshot_dir.exists():
        logger.warning("Snapshot dir %s does not exist; cannot restore", snapshot_dir)
        return
    if run_engine_dir.exists():
        shutil.rmtree(run_engine_dir)
    shutil.copytree(snapshot_dir, run_engine_dir)
    # Clean up the snapshot after successful restore
    shutil.rmtree(snapshot_dir)


def commit_engine_changes(workspace: Path, run_engine_dir: Path) -> list[str]:
    """Commit engine changes from a card workspace back to the run engine.

    Compares files in ``<workspace>/engine/`` against *run_engine_dir*
    and copies any new or modified files back.

    Parameters
    ----------
    workspace:
        The card's workspace directory (contains ``engine/``).
    run_engine_dir:
        The persistent run-level engine directory.

    Returns
    -------
    list[str]
        List of relative paths that were updated.
    """
    card_engine = workspace / "engine"
    if not card_engine.exists():
        return []

    updated: list[str] = []
    for dirpath, _dirs, files in os.walk(card_engine):
        for fname in files:
            src = Path(dirpath) / fname
            rel = src.relative_to(card_engine)
            dst = run_engine_dir / rel
            # Copy if new or content differs
            if not dst.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                updated.append(str(rel))
            else:
                if src.read_bytes() != dst.read_bytes():
                    shutil.copy2(src, dst)
                    updated.append(str(rel))

    # Handle deletions: files in run_engine but not in card engine
    for dirpath, _dirs, files in os.walk(run_engine_dir):
        for fname in files:
            dst = Path(dirpath) / fname
            rel = dst.relative_to(run_engine_dir)
            src = card_engine / rel
            if not src.exists():
                dst.unlink()
                updated.append(f"-{rel}")

    return updated


def compute_engine_diff(
    workspace: Path,
    run_engine_dir: Path,
    results_dir: Path,
) -> Path:
    """Compute a diff between a card's engine and the run-level engine.

    Compares files in ``<workspace>/engine/`` against *run_engine_dir*
    and writes a unified-diff patch to ``<results_dir>/engine_diff.patch``.

    Handles new files, deleted files, modified files, and binary files.
    If there are no differences an empty patch file is still created.

    Parameters
    ----------
    workspace:
        The card's workspace directory (contains ``engine/``).
    run_engine_dir:
        The persistent run-level engine directory.
    results_dir:
        Card results directory where ``engine_diff.patch`` is written.

    Returns
    -------
    Path
        Path to the written patch file.
    """
    card_engine = workspace / "engine"
    patch_path = results_dir / "engine_diff.patch"
    results_dir.mkdir(parents=True, exist_ok=True)

    hunks: list[str] = []

    # Collect all relative paths from both sides
    run_files: set[str] = set()
    card_files: set[str] = set()

    if run_engine_dir.exists():
        for dirpath, _dirs, files in os.walk(run_engine_dir):
            for fname in files:
                rel = str(Path(dirpath, fname).relative_to(run_engine_dir))
                run_files.add(rel)

    if card_engine.exists():
        for dirpath, _dirs, files in os.walk(card_engine):
            for fname in files:
                rel = str(Path(dirpath, fname).relative_to(card_engine))
                card_files.add(rel)

    all_paths = sorted(run_files | card_files)

    for rel in all_paths:
        run_path = run_engine_dir / rel
        card_path = card_engine / rel

        a_label = f"a/engine/{rel}"
        b_label = f"b/engine/{rel}"

        if rel not in run_files:
            # New file added in card workspace
            try:
                new_bytes = card_path.read_bytes()
            except Exception:
                hunks.append(
                    f"Binary file {b_label} added\n"
                )
                continue
            if b"\x00" in new_bytes:
                hunks.append(
                    f"Binary file {b_label} added\n"
                )
                continue
            new_lines = new_bytes.decode(errors="replace").splitlines(
                keepends=True
            )
            diff = difflib.unified_diff(
                [], new_lines, fromfile="/dev/null", tofile=b_label
            )
            chunk = "".join(diff)
            if chunk:
                hunks.append(chunk)
        elif rel not in card_files:
            # File deleted in card workspace
            try:
                old_bytes = run_path.read_bytes()
            except Exception:
                hunks.append(
                    f"Binary file {a_label} deleted\n"
                )
                continue
            if b"\x00" in old_bytes:
                hunks.append(
                    f"Binary file {a_label} deleted\n"
                )
                continue
            old_lines = old_bytes.decode(errors="replace").splitlines(
                keepends=True
            )
            diff = difflib.unified_diff(
                old_lines, [], fromfile=a_label, tofile="/dev/null"
            )
            chunk = "".join(diff)
            if chunk:
                hunks.append(chunk)
        else:
            # Both exist – check for differences
            try:
                old_bytes = run_path.read_bytes()
                new_bytes = card_path.read_bytes()
            except Exception:
                continue

            if old_bytes == new_bytes:
                continue

            # Check if binary
            if b"\x00" in old_bytes or b"\x00" in new_bytes:
                hunks.append(
                    f"Binary files {a_label} and {b_label} differ\n"
                )
                continue

            old_lines = old_bytes.decode(errors="replace").splitlines(
                keepends=True
            )
            new_lines = new_bytes.decode(errors="replace").splitlines(
                keepends=True
            )
            diff = difflib.unified_diff(
                old_lines, new_lines, fromfile=a_label, tofile=b_label
            )
            chunk = "".join(diff)
            if chunk:
                hunks.append(chunk)

    patch_path.write_text("".join(hunks))
    return patch_path


def save_engine_final(run_engine_dir: Path, output_dir: str | Path) -> Path:
    """Save the final engine state as a run artifact.

    Copies the run-level engine directory to
    ``<output_dir>/engine_final/``.

    Parameters
    ----------
    run_engine_dir:
        The persistent run-level engine directory.
    output_dir:
        Top-level output directory for the benchmark run.

    Returns
    -------
    Path
        Path to the saved engine artifact.
    """
    output_dir = Path(output_dir)
    engine_final = output_dir / "engine_final"
    if engine_final.exists():
        shutil.rmtree(engine_final)
    shutil.copytree(run_engine_dir, engine_final)
    return engine_final


# ---------------------------------------------------------------------------
# Standalone convenience functions (match TODO contract names)
# ---------------------------------------------------------------------------


def setup_workspace(
    card_name: str,
    config: BenchmarkConfig,
    card_spec: dict[str, Any],
    card_dir: str,
    run_engine_dir: Path | None = None,
) -> AgentSession:
    """Create a session and set up its workspace.

    Convenience wrapper that constructs an ``AgentSession``, calls
    ``setup_workspace()``, and returns the session.
    """
    session = AgentSession(
        config=config,
        card_spec=card_spec,
        card_dir=card_dir,
        run_engine_dir=run_engine_dir,
    )
    session.setup_workspace()
    return session


def run_blind(session: AgentSession) -> BlindResult:
    """Run the blind implementation phase via strategy delegation.

    Delegates to ``session.run_card()`` (blind mode).
    """
    if session.workspace is None:
        msg = "Workspace not set up — call setup_workspace first"
        raise RuntimeError(msg)
    result = session.run_card()
    impl_path = session.workspace / "card_impl.py" if session.workspace else None
    return BlindResult(
        impl_path=impl_path if impl_path and impl_path.exists() else None,
        tokens=0,
        runtime_seconds=result.runtime_ms / 1000 if result.runtime_ms else 0,
        peak_context=0,
        status=result.status.value,
    )


def run_test_informed(session: AgentSession, blind_impl: Path) -> TestInformedResult:
    """Run the test-informed implementation phase via strategy delegation.

    Delegates to ``session.run_card()`` (impl_test mode).
    """
    if session.workspace is None:
        msg = "Workspace not set up — call setup_workspace first"
        raise RuntimeError(msg)
    result = session.run_card()
    ws = session.workspace
    return TestInformedResult(
        impl_path=ws / "card_impl.py" if ws and (ws / "card_impl.py").exists() else None,
        tests_path=ws / "tests.py" if ws and (ws / "tests.py").exists() else None,
        iterations=1,
        tokens=0,
        runtime_seconds=result.runtime_ms / 1000 if result.runtime_ms else 0,
        peak_context=0,
        status=result.status.value,
    )


def cleanup(session: AgentSession) -> None:
    """Remove the session's temporary workspace."""
    session.cleanup()
