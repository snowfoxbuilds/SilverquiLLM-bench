"""Agent session manager for per-card benchmark runs.

Manages workspace setup, OpenCode configuration, and the two-phase
implementation flow (blind → test-informed) with contamination controls.

Public API:
- ``AgentSession`` — dataclass orchestrating a single card's benchmark run.
- ``BlindResult`` / ``TestInformedResult`` — result dataclasses.
- Standalone helpers: ``setup_workspace``, ``write_opencode_config``,
  ``run_blind``, ``run_test_informed``, ``cleanup``.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from benchmark.config import BenchmarkConfig
from benchmark.prompts import (
    blind_implementation_prompt,
    iteration_feedback_prompt,
    test_informed_prompt,
)
from benchmark.template_gen import generate_template

logger = logging.getLogger(__name__)

__all__ = [
    "AgentSession",
    "BlindResult",
    "TestInformedResult",
    "setup_workspace",
    "write_opencode_config",
    "run_blind",
    "run_test_informed",
    "cleanup",
]

# Repo root — resolved once at import time
_REPO_ROOT = Path(__file__).resolve().parent.parent


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
    _workspace: Path | None = field(default=None, init=False, repr=False)
    _opencode_cfg_path: Path | None = field(default=None, init=False, repr=False)

    # -- Convenience properties matching TODO contract names ----------------

    @property
    def card_name(self) -> str:
        """Card name derived from the spec."""
        return self.card_spec.get("name", "")

    @property
    def workspace(self) -> Path | None:
        """Current workspace path (None before setup)."""
        return self._workspace

    @property
    def opencode_cfg_path(self) -> Path | None:
        """Path to the written ``.opencode.yaml`` (None before write)."""
        return self._opencode_cfg_path

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
        workspace = Path(tempfile.mkdtemp(prefix="bench_agent_"))
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
        card_py = repo_root / "engine" / "card.py"
        if card_py.exists():
            base_classes_content = _extract_base_classes(card_py)
            (workspace / "base_classes.py").write_text(base_classes_content)

        # 4. template.py — generated for this card
        template_source = generate_template(self.card_spec)
        (workspace / "template.py").write_text(template_source)

        # 5. rules_overview.md
        rules_src = repo_root / "benchmarks" / "sos" / "data" / "rules_overview.md"
        if rules_src.exists():
            shutil.copy2(rules_src, workspace / "rules_overview.md")

        # 6. foundations/ — read-only copy
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

        logger.info("Workspace created at %s", workspace)
        return workspace

    # ------------------------------------------------------------------
    # OpenCode configuration
    # ------------------------------------------------------------------

    def configure_opencode(self, workspace: Path) -> dict[str, Any]:
        """Return OpenCode configuration dict with contamination controls.

        Permissions:
        - Deny web fetch / network access.
        - Allow only workspace directory reads/writes.

        Parameters
        ----------
        workspace:
            The workspace directory to scope permissions to.

        Returns
        -------
        dict
            OpenCode-compatible configuration dictionary.
        """
        cfg = {
            "model": self.config.model_name,
            "provider": self.config.model_provider,
            "temperature": self.config.temperature,
            "max_context": self.config.max_context,
            "working_directory": str(workspace),
            "repo_root": str(_REPO_ROOT),
            "engine_path": str(_REPO_ROOT / "engine"),
            "permissions": {
                "deny_web_fetch": True,
                "deny_network": True,
                "allow_read": [str(workspace), str(_REPO_ROOT / "engine")],
                "allow_write": [str(workspace)],
            },
            "timeout": self.config.timeout_per_card,
        }
        return cfg

    # ------------------------------------------------------------------
    # OpenCode invocation (swappable)
    # ------------------------------------------------------------------

    def _run_opencode(self, prompt: str, workspace: Path) -> str:
        """Run an OpenCode session with the given prompt.

        This method wraps ``subprocess.run`` and can be monkey-patched or
        overridden in tests to avoid actual subprocess calls.

        Parameters
        ----------
        prompt:
            The full prompt text to send to OpenCode.
        workspace:
            Working directory for the subprocess.

        Returns
        -------
        str
            Raw stdout from OpenCode.

        Raises
        ------
        subprocess.TimeoutExpired
            When the process exceeds timeout_per_card seconds.
        """
        config = self.configure_opencode(workspace)
        config_path = workspace / ".opencode.yaml"
        # Write as YAML-compatible JSON (valid YAML subset)
        config_path.write_text(json.dumps(config, indent=2))
        self._opencode_cfg_path = config_path

        prompt_path = workspace / ".prompt.txt"
        prompt_path.write_text(prompt)

        result = subprocess.run(
            ["opencode", "--config", str(config_path), "--prompt", str(prompt_path)],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=self.config.timeout_per_card,
        )
        return result.stdout

    # ------------------------------------------------------------------
    # Step 1 — Blind implementation
    # ------------------------------------------------------------------

    def run_blind_implementation(self, workspace: Path) -> BlindResult:
        """Run Step 1: blind implementation.

        Launches OpenCode with the blind implementation prompt.  Collects
        output as ``blind_impl.py``, records token counts and timing.

        Parameters
        ----------
        workspace:
            Path to the prepared workspace directory.

        Returns
        -------
        BlindResult
        """
        prompt = blind_implementation_prompt(self.card_spec)
        start = time.monotonic()

        try:
            output = self._run_opencode(prompt, workspace)
        except subprocess.TimeoutExpired:
            return BlindResult(
                impl_path=None,
                tokens=0,
                runtime_seconds=time.monotonic() - start,
                peak_context=0,
                status="timeout",
            )

        elapsed = time.monotonic() - start

        # Look for implementation file produced by the agent
        impl_path = workspace / "blind_impl.py"

        # Only consider blind_impl.py if the agent actually created it.
        # Do NOT copy the starter template — that would be a false positive.

        if not impl_path.exists():
            return BlindResult(
                impl_path=None,
                tokens=0,
                runtime_seconds=elapsed,
                peak_context=0,
                status="no_output",
            )

        # Validate syntax
        source = impl_path.read_text()
        try:
            compile(source, str(impl_path), "exec")
        except SyntaxError:
            # Feed to correction round — but for blind phase, just record
            return BlindResult(
                impl_path=impl_path,
                tokens=_estimate_tokens(output),
                runtime_seconds=elapsed,
                peak_context=_estimate_tokens(prompt + output),
                status="syntax_error",
            )

        # Check for violations (writing outside workspace)
        if _check_violations(workspace):
            return BlindResult(
                impl_path=None,
                tokens=_estimate_tokens(output),
                runtime_seconds=elapsed,
                peak_context=_estimate_tokens(prompt + output),
                status="violation",
            )

        tokens = _estimate_tokens(output)
        peak = _estimate_tokens(prompt + output)

        return BlindResult(
            impl_path=impl_path,
            tokens=tokens,
            runtime_seconds=elapsed,
            peak_context=peak,
            status="ok",
        )

    # ------------------------------------------------------------------
    # Step 2 — Test-informed implementation
    # ------------------------------------------------------------------

    def run_test_informed(
        self,
        workspace: Path,
        blind_impl: Path,
    ) -> TestInformedResult:
        """Run Step 2: test-informed implementation with iteration.

        Injects ``test_utils.md``, launches Step 2 prompt, iterates up to
        ``max_test_rounds`` times (running pytest between rounds and
        feeding results back).

        Parameters
        ----------
        workspace:
            Path to the prepared workspace directory.
        blind_impl:
            Path to the blind implementation file from Step 1.

        Returns
        -------
        TestInformedResult
        """
        repo_root = _REPO_ROOT

        # Inject test_utils.md
        test_utils_src = repo_root / "docs" / "test_utils.md"
        if test_utils_src.exists():
            shutil.copy2(test_utils_src, workspace / "test_utils.md")

        # Copy blind impl as card_impl.py for the agent to work from
        card_impl_path = workspace / "card_impl.py"
        if blind_impl.exists():
            shutil.copy2(blind_impl, card_impl_path)

        total_tokens = 0
        peak_context = 0
        rules_lookups = 0
        iterations = 0
        tests_passed = False
        start = time.monotonic()

        prompt = test_informed_prompt(self.card_spec, round_num=1)

        for round_num in range(1, self.config.max_test_rounds + 1):
            iterations = round_num

            try:
                output = self._run_opencode(prompt, workspace)
            except subprocess.TimeoutExpired:
                return TestInformedResult(
                    impl_path=card_impl_path if card_impl_path.exists() else None,
                    tests_path=workspace / "tests.py" if (workspace / "tests.py").exists() else None,
                    iterations=iterations,
                    tokens=total_tokens,
                    runtime_seconds=time.monotonic() - start,
                    peak_context=peak_context,
                    rules_lookups=rules_lookups,
                    status="timeout",
                )

            round_tokens = _estimate_tokens(output)
            total_tokens += round_tokens
            peak_context = max(peak_context, _estimate_tokens(prompt + output))
            rules_lookups += _count_rules_lookups(output)

            # Check for test file
            tests_path = workspace / "tests.py"
            impl_path = workspace / "tested_impl.py"

            # Agent may update card_impl.py directly
            if not impl_path.exists() and card_impl_path.exists():
                impl_path = card_impl_path

            if not tests_path.exists():
                # No tests produced yet — continue if more rounds
                if round_num < self.config.max_test_rounds:
                    prompt = test_informed_prompt(
                        self.card_spec, round_num=round_num + 1
                    )
                    continue

            # Run pytest on the tests
            if tests_path.exists():
                test_result = self._run_pytest(workspace, tests_path)

                # All passing → done
                if test_result.returncode == 0:
                    tests_passed = True
                    break

                # More rounds available → feed back
                if round_num < self.config.max_test_rounds:
                    prompt = iteration_feedback_prompt(
                        test_output=test_result.stdout + test_result.stderr,
                        round_num=round_num,
                        max_rounds=self.config.max_test_rounds,
                    )
                    continue

        elapsed = time.monotonic() - start

        # Determine final paths
        final_impl = None
        if (workspace / "tested_impl.py").exists():
            final_impl = workspace / "tested_impl.py"
        elif card_impl_path.exists():
            final_impl = card_impl_path

        final_tests = workspace / "tests.py" if (workspace / "tests.py").exists() else None

        # Determine final status
        final_status = "ok" if tests_passed else "max_rounds_exhausted"

        return TestInformedResult(
            impl_path=final_impl,
            tests_path=final_tests,
            iterations=iterations,
            tokens=total_tokens,
            runtime_seconds=elapsed,
            peak_context=peak_context,
            rules_lookups=rules_lookups,
            status=final_status,
        )

    # ------------------------------------------------------------------
    # Pytest runner
    # ------------------------------------------------------------------

    def _run_pytest(
        self,
        workspace: Path,
        tests_path: Path,
    ) -> subprocess.CompletedProcess[str]:
        """Run pytest on a test file within the workspace.

        Parameters
        ----------
        workspace:
            Working directory.
        tests_path:
            Path to the test file.

        Returns
        -------
        subprocess.CompletedProcess
        """
        return subprocess.run(
            ["python", "-m", "pytest", str(tests_path), "-v", "--tb=short"],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=60,
        )

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup(self) -> None:
        """Remove the temporary workspace directory."""
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
# Helpers
# ---------------------------------------------------------------------------


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token."""
    return len(text) // 4


def _count_rules_lookups(output: str) -> int:
    """Count references to rules lookups in agent output."""
    # Pattern matches lines like "Looking up rule 702.3" or "rules_lookup"
    return len(re.findall(r"(?:rules?_?lookup|looking up rule)", output, re.IGNORECASE))


def _check_violations(workspace: Path) -> bool:
    """Check if any files were modified outside the workspace.

    For now, this is a placeholder — real implementation would compare
    filesystem state before/after the agent run.
    """
    return False


# ---------------------------------------------------------------------------
# Standalone convenience functions (match TODO contract names)
# ---------------------------------------------------------------------------


def setup_workspace(card_name: str, config: BenchmarkConfig, card_spec: dict[str, Any], card_dir: str) -> AgentSession:
    """Create a session and set up its workspace.

    Convenience wrapper that constructs an ``AgentSession``, calls
    ``setup_workspace()``, and returns the session.
    """
    session = AgentSession(config=config, card_spec=card_spec, card_dir=card_dir)
    session.setup_workspace()
    return session


def write_opencode_config(session: AgentSession) -> Path:
    """Write ``.opencode.yaml`` into the session workspace.

    Returns the path to the written config file.
    """
    if session.workspace is None:
        msg = "Workspace not set up — call setup_workspace first"
        raise RuntimeError(msg)
    cfg = session.configure_opencode(session.workspace)
    cfg_path = session.workspace / ".opencode.yaml"
    cfg_path.write_text(json.dumps(cfg, indent=2))
    session._opencode_cfg_path = cfg_path
    return cfg_path


def run_blind(session: AgentSession) -> BlindResult:
    """Run the blind implementation phase.

    Delegates to ``session.run_blind_implementation``.
    """
    if session.workspace is None:
        msg = "Workspace not set up — call setup_workspace first"
        raise RuntimeError(msg)
    return session.run_blind_implementation(session.workspace)


def run_test_informed(session: AgentSession, tests: Path) -> TestInformedResult:
    """Run the test-informed implementation phase.

    Delegates to ``session.run_test_informed``.
    """
    if session.workspace is None:
        msg = "Workspace not set up — call setup_workspace first"
        raise RuntimeError(msg)
    return session.run_test_informed(session.workspace, tests)


def cleanup(session: AgentSession) -> None:
    """Remove the session's temporary workspace."""
    session.cleanup()
