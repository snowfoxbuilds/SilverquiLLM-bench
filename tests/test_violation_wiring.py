"""Tests for TODO item 2: Wire enhanced violation checks into run methods.

Validates that run_blind_implementation and run_test_informed correctly use
_snapshot_all_protected and _check_violations to detect and report contamination.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from silverquillm.agent_session import (
    AgentSession,
    BlindResult,
    TestInformedResult,
    run_blind,
    run_test_informed,
)
from silverquillm.config import AgentConfig, BenchmarkConfig


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_config(**overrides) -> BenchmarkConfig:
    defaults = dict(
        name="test-bench",
        set_code="FDN",
        model_name="test-model",
        model_provider="test-provider",
        max_context=200_000,
        temperature=0.0,
        agent=AgentConfig(
            max_test_rounds=3,
            timeout_per_card=300,
        ),
    )
    defaults.update(overrides)
    return BenchmarkConfig(**defaults)


_SAMPLE_SPEC = {
    "name": "Grizzly Bears",
    "mana_cost": "{1}{G}",
    "type_line": "Creature — Bear",
    "oracle_text": "",
    "power": "2",
    "toughness": "2",
}


@pytest.fixture()
def fake_repo(tmp_path):
    """Create a fake repo root with protected directories."""
    repo = tmp_path / "repo"
    repo.mkdir()
    # Create protected dirs with at least one file each
    for dirname in ("engine", "cards", "tests", "benchmark", "benchmarks", "docs"):
        d = repo / dirname
        d.mkdir()
        (d / "existing.py").write_text(f"# {dirname}\n")
    return repo


@pytest.fixture()
def session(fake_repo):
    """Create a session with a fake card_dir and patched _REPO_ROOT."""
    card_dir = fake_repo / "card_data"
    card_dir.mkdir()
    (card_dir / "card_spec.json").write_text(json.dumps(_SAMPLE_SPEC))

    config = _make_config()
    sess = AgentSession(config=config, card_spec=_SAMPLE_SPEC, card_dir=str(card_dir))
    yield sess
    sess.cleanup()


# ---------------------------------------------------------------------------
# run_blind_implementation — violation detection
# ---------------------------------------------------------------------------


class TestRunBlindViolationDetection:
    """run_blind_implementation must detect writes to protected dirs."""

    def test_violation_when_agent_writes_to_docs(self, session, fake_repo):
        """Agent creating a file in docs/ should result in status='violation'."""
        ws = session.setup_workspace()

        def fake_opencode(prompt, workspace):
            # Agent produces valid output
            (workspace / "blind_impl.py").write_text("x = 1\n")
            # But also writes to a protected directory
            (fake_repo / "docs" / "hack.py").write_text("# hacked\n")
            return "some output"

        with patch("silverquillm.agent_session._REPO_ROOT", fake_repo):
            session._run_agent = fake_opencode
            result = session.run_blind_implementation(ws)

        assert isinstance(result, BlindResult)
        assert result.status == "violation"
        assert result.impl_path is None

    def test_violation_when_agent_modifies_existing_protected_file(self, session, fake_repo):
        """Agent modifying an existing file in a protected dir → violation."""
        ws = session.setup_workspace()

        def fake_opencode(prompt, workspace):
            (workspace / "blind_impl.py").write_text("x = 1\n")
            # Modify existing file in protected dir
            (fake_repo / "tests" / "existing.py").write_text("# modified\n")
            return "output"

        with patch("silverquillm.agent_session._REPO_ROOT", fake_repo):
            session._run_agent = fake_opencode
            result = session.run_blind_implementation(ws)

        assert result.status == "violation"

    def test_no_violation_when_agent_only_writes_in_workspace(self, session, fake_repo):
        """Agent writing only in workspace should return status='ok'."""
        ws = session.setup_workspace()

        def fake_opencode(prompt, workspace):
            (workspace / "blind_impl.py").write_text("x = 1\n")
            return "output"

        with patch("silverquillm.agent_session._REPO_ROOT", fake_repo):
            session._run_agent = fake_opencode
            result = session.run_blind_implementation(ws)

        assert result.status == "ok"
        assert result.impl_path is not None

    def test_violation_records_tokens(self, session, fake_repo):
        """Even on violation, tokens should be estimated from output."""
        ws = session.setup_workspace()

        def fake_opencode(prompt, workspace):
            (workspace / "blind_impl.py").write_text("x = 1\n")
            (fake_repo / "docs" / "hack.py").write_text("bad\n")
            return "a" * 400  # ~100 tokens

        with patch("silverquillm.agent_session._REPO_ROOT", fake_repo):
            session._run_agent = fake_opencode
            result = session.run_blind_implementation(ws)

        assert result.status == "violation"
        assert result.tokens > 0


# ---------------------------------------------------------------------------
# run_test_informed — violation detection
# ---------------------------------------------------------------------------


class TestRunTestInformedViolationDetection:
    """run_test_informed must detect violations after each agent invocation."""

    def _setup_blind(self, ws):
        blind = ws / "blind_impl.py"
        blind.write_text("x = 1\n")
        return blind

    def test_violation_on_first_round(self, session, fake_repo):
        """Violation on the first round should immediately return violation status."""
        ws = session.setup_workspace()
        blind_impl = self._setup_blind(ws)

        def fake_opencode(prompt, workspace):
            (workspace / "tests.py").write_text("def test_pass(): pass\n")
            # Write to protected dir
            (fake_repo / "docs" / "hack.py").write_text("# hacked\n")
            return "output"

        with patch("silverquillm.agent_session._REPO_ROOT", fake_repo):
            session._run_agent = fake_opencode
            result = session.run_test_informed(ws, blind_impl)

        assert isinstance(result, TestInformedResult)
        assert result.status == "violation"
        assert result.iterations == 1

    def test_violation_on_later_round(self, session, fake_repo):
        """Violation on round 2+ should return violation with correct iteration count."""
        ws = session.setup_workspace()
        blind_impl = self._setup_blind(ws)
        call_count = [0]

        def fake_opencode(prompt, workspace):
            call_count[0] += 1
            if call_count[0] == 1:
                # First round: clean, produces tests that fail
                (workspace / "tests.py").write_text("def test_fail(): assert False\n")
                (workspace / "card_impl.py").write_text("x = 1\n")
                return "output round 1"
            else:
                # Second round: violates
                (workspace / "tests.py").write_text("def test_pass(): pass\n")
                (fake_repo / "cards" / "evil.py").write_text("# evil\n")
                return "output round 2"

        def fake_pytest(workspace, tests_path):
            # Always fail so we iterate
            return subprocess.CompletedProcess(
                args=[], returncode=1, stdout="FAILED", stderr=""
            )

        with patch("silverquillm.agent_session._REPO_ROOT", fake_repo):
            session._run_agent = fake_opencode
            session._run_pytest = fake_pytest
            result = session.run_test_informed(ws, blind_impl)

        assert result.status == "violation"
        assert result.iterations == 2

    def test_no_violation_when_clean(self, session, fake_repo):
        """No violation when agent only writes in workspace → ok status."""
        ws = session.setup_workspace()
        blind_impl = self._setup_blind(ws)

        def fake_opencode(prompt, workspace):
            (workspace / "tests.py").write_text("def test_pass(): pass\n")
            (workspace / "tested_impl.py").write_text("x = 2\n")
            return "output"

        def fake_pytest(workspace, tests_path):
            return subprocess.CompletedProcess(
                args=[], returncode=0, stdout="passed", stderr=""
            )

        with patch("silverquillm.agent_session._REPO_ROOT", fake_repo):
            session._run_agent = fake_opencode
            session._run_pytest = fake_pytest
            result = session.run_test_informed(ws, blind_impl)

        assert result.status == "ok"

    def test_violation_returns_impl_path_if_exists(self, session, fake_repo):
        """On violation, impl_path should still be populated if file exists."""
        ws = session.setup_workspace()
        blind_impl = self._setup_blind(ws)

        def fake_opencode(prompt, workspace):
            (workspace / "tests.py").write_text("def test_pass(): pass\n")
            (workspace / "card_impl.py").write_text("x = 1\n")
            (fake_repo / "docs" / "hack.md").write_text("# hacked\n")
            return "output"

        with patch("silverquillm.agent_session._REPO_ROOT", fake_repo):
            session._run_agent = fake_opencode
            result = session.run_test_informed(ws, blind_impl)

        assert result.status == "violation"
        # card_impl.py exists, so impl_path should be set
        assert result.impl_path is not None

    def test_violation_takes_snapshot_each_round(self, session, fake_repo):
        """Snapshot is fresh each round — a file created in round 1 doesn't trigger in round 2."""
        ws = session.setup_workspace()
        blind_impl = self._setup_blind(ws)
        call_count = [0]

        def fake_opencode(prompt, workspace):
            call_count[0] += 1
            if call_count[0] == 1:
                # Round 1: clean (just produce failing tests)
                (workspace / "tests.py").write_text("def test_fail(): assert False\n")
                (workspace / "card_impl.py").write_text("x = 1\n")
                return "round 1"
            else:
                # Round 2: also clean, tests pass
                (workspace / "tests.py").write_text("def test_pass(): pass\n")
                (workspace / "tested_impl.py").write_text("x = 2\n")
                return "round 2"

        def fake_pytest(workspace, tests_path):
            if call_count[0] == 1:
                return subprocess.CompletedProcess(
                    args=[], returncode=1, stdout="FAILED", stderr=""
                )
            return subprocess.CompletedProcess(
                args=[], returncode=0, stdout="passed", stderr=""
            )

        with patch("silverquillm.agent_session._REPO_ROOT", fake_repo):
            session._run_agent = fake_opencode
            session._run_pytest = fake_pytest
            result = session.run_test_informed(ws, blind_impl)

        assert result.status == "ok"
        assert result.iterations == 2
