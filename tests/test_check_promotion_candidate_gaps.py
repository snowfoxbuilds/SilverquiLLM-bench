"""Additional gap tests for scripts/check_promotion_candidate.py.

Covers genuine gaps NOT addressed by test_check_promotion_candidate.py:

1. check_canonical_api — unparseable candidate (SyntaxError) → fail-closed.
2. check_canonical_api — engine dir missing (no crash), still evaluates gracefully.
3. Orchestrator aggregates both canonical-API failure AND oracle pass → not allowed.
4. main() prints each failing check reason to stdout and ADR-011 note to stderr.
5. Exit code is non-zero when only the canonical-API check fails (oracle passes).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from io import StringIO
from pathlib import Path
from unittest import mock

import pytest

# ---------------------------------------------------------------------------
# Import the script module via importlib (scripts/ is not a package)
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT_PATH = REPO_ROOT / "scripts" / "check_promotion_candidate.py"

_spec = importlib.util.spec_from_file_location(
    "check_promotion_candidate", _SCRIPT_PATH
)
_mod = importlib.util.module_from_spec(_spec)
# Reuse cached module if already loaded
if "check_promotion_candidate" not in sys.modules:
    sys.modules["check_promotion_candidate"] = _mod
    _spec.loader.exec_module(_mod)
else:
    _mod = sys.modules["check_promotion_candidate"]

check_canonical_api = _mod.check_canonical_api
check_promotion_candidate = _mod.check_promotion_candidate
main = _mod.main
_MAINTAINER_NOTE = _mod._MAINTAINER_NOTE


# ---------------------------------------------------------------------------
# Helpers (mirrors helpers in the Tester's file; copied for isolation)
# ---------------------------------------------------------------------------


def _write_config(root: Path, bench: str, tier: str) -> None:
    cfg_dir = root / "benchmarks" / bench
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "config.json").write_text(json.dumps({"tier": tier}))


def _write_candidate(root: Path, content: str, name: str = "test_candidate.py") -> Path:
    candidate = root / name
    candidate.write_text(content)
    return candidate


def _build_engine(engine_dir: Path, symbols: dict[str, str]) -> None:
    engine_dir.mkdir(parents=True, exist_ok=True)
    for mod_name, source in symbols.items():
        (engine_dir / f"{mod_name}.py").write_text(source)


# ---------------------------------------------------------------------------
# Gap 1: check_canonical_api on an unparseable candidate (SyntaxError)
# ---------------------------------------------------------------------------


class TestCheckCanonicalApiSyntaxError:
    """check_canonical_api must handle a candidate that cannot be parsed."""

    def test_syntax_error_candidate_fails_closed(self, tmp_path: Path) -> None:
        """Candidate with invalid Python syntax → fail-closed (ok=False)."""
        _build_engine(
            tmp_path / "benchmarks" / "sos" / "workspace" / "engine",
            {"game": "def create_game(): pass\n"},
        )
        _build_engine(
            tmp_path / "benchmarks" / "sos" / "data" / "test_oracle_workspace" / "engine",
            {"game": "def create_game(): pass\n"},
        )

        # Write a file with a Python syntax error
        bad_candidate = tmp_path / "bad_tests.py"
        bad_candidate.write_text("def test_x(:\n    pass\n")  # invalid syntax

        ok, reason = check_canonical_api(bad_candidate, tmp_path, bench="sos")

        assert ok is False, "Unparseable candidate should fail-closed"
        # Reason should mention parse failure
        reason_lower = reason.lower()
        assert "parse" in reason_lower or "failed" in reason_lower or "syntax" in reason_lower, (
            f"Expected failure reason to mention parse/syntax problem; got: {reason!r}"
        )

    def test_syntax_error_candidate_reason_mentions_path(self, tmp_path: Path) -> None:
        """Failure reason for SyntaxError should reference the candidate file path."""
        _build_engine(
            tmp_path / "benchmarks" / "sos" / "workspace" / "engine",
            {"game": "def create_game(): pass\n"},
        )
        _build_engine(
            tmp_path / "benchmarks" / "sos" / "data" / "test_oracle_workspace" / "engine",
            {"game": "def create_game(): pass\n"},
        )

        bad_candidate = tmp_path / "broken.py"
        bad_candidate.write_text("def bad((\n")

        ok, reason = check_canonical_api(bad_candidate, tmp_path, bench="sos")

        assert ok is False
        # The reason should include the file path so the user knows which file failed
        assert str(bad_candidate) in reason or "broken.py" in reason, (
            f"Expected reason to mention file path; got: {reason!r}"
        )


# ---------------------------------------------------------------------------
# Gap 2: check_canonical_api when engine dir is missing (no crash)
# ---------------------------------------------------------------------------


class TestCheckCanonicalApiMissingEngineDir:
    """check_canonical_api must not crash when one or both engine dirs are absent."""

    def test_both_engine_dirs_missing_passes(self, tmp_path: Path) -> None:
        """Neither canonical nor oracle engine dir exists → no oracle-only symbols → ok."""
        candidate = _write_candidate(tmp_path, "def test_it():\n    pass\n")

        # Neither engine dir created
        ok, reason = check_canonical_api(candidate, tmp_path, bench="sos")

        assert ok is True, (
            "When both engine dirs are missing there are no oracle-only symbols, so candidate passes"
        )

    def test_canonical_missing_oracle_has_symbols_rejects(self, tmp_path: Path) -> None:
        """Oracle engine exists with symbols, canonical missing → oracle-only symbols exist.

        If the candidate references one of those oracle-only symbols, it must be rejected.
        """
        # Only oracle engine exists
        _build_engine(
            tmp_path / "benchmarks" / "sos" / "data" / "test_oracle_workspace" / "engine",
            {"game": "def oracle_fn(): pass\n"},
        )
        # Canonical dir intentionally absent

        candidate = _write_candidate(
            tmp_path,
            "def test_it():\n    oracle_fn()\n",
        )

        ok, reason = check_canonical_api(candidate, tmp_path, bench="sos")

        assert ok is False, (
            "oracle_fn is oracle-only (canonical engine missing); candidate should be rejected"
        )
        assert "oracle_fn" in reason

    def test_oracle_missing_canonical_has_symbols_passes(self, tmp_path: Path) -> None:
        """Canonical engine exists, oracle engine dir missing → no oracle-only symbols → ok."""
        _build_engine(
            tmp_path / "benchmarks" / "sos" / "workspace" / "engine",
            {"game": "def create_game(): pass\n"},
        )
        # Oracle dir intentionally absent

        candidate = _write_candidate(
            tmp_path,
            "def test_it():\n    create_game()\n",
        )

        ok, reason = check_canonical_api(candidate, tmp_path, bench="sos")

        assert ok is True, (
            "With no oracle engine there are no oracle-only symbols; candidate should pass"
        )


# ---------------------------------------------------------------------------
# Gap 3: Orchestrator — canonical-API fails, oracle passes → not allowed
# ---------------------------------------------------------------------------


class TestOrchestratorCanonicalFailOraclePass:
    """Canonical-API check fails but oracle passes → overall result must be not allowed."""

    def test_canonical_fail_oracle_pass_not_allowed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ALL checks must pass; canonical fail alone must block promotion."""
        _write_config(tmp_path, "sos", "benchmarking")

        # Canonical engine: only create_game
        _build_engine(
            tmp_path / "benchmarks" / "sos" / "workspace" / "engine",
            {"game": "def create_game(): pass\n"},
        )
        # Oracle engine: create_game + oracle_only_fn
        _build_engine(
            tmp_path / "benchmarks" / "sos" / "data" / "test_oracle_workspace" / "engine",
            {"game": "def create_game(): pass\ndef oracle_only_fn(): pass\n"},
        )

        # Candidate references oracle_only_fn → canonical-API check fails
        candidate = _write_candidate(
            tmp_path,
            "def test_it():\n    oracle_only_fn()\n",
        )

        # Oracle gate monkeypatched to pass
        monkeypatch.setattr(
            _mod, "check_oracle_gate", lambda *a, **k: (True, "mock oracle pass")
        )

        result = check_promotion_candidate(candidate, "sos_1", tmp_path, bench="sos")

        assert result.allowed is False, (
            "Promotion must be blocked when canonical-API check fails, even if oracle passes"
        )

        # Verify canonical-API check is present and failed
        api_checks = [c for c in result.checks if c.name == "canonical_api"]
        assert len(api_checks) == 1
        assert api_checks[0].ok is False
        assert "oracle_only_fn" in api_checks[0].reason

        # Verify oracle check is present and passed (both checks run per spec)
        oracle_checks = [c for c in result.checks if c.name == "oracle_gate"]
        assert len(oracle_checks) == 1
        assert oracle_checks[0].ok is True

        # Tier check passed
        tier_checks = [c for c in result.checks if c.name == "tier"]
        assert len(tier_checks) == 1
        assert tier_checks[0].ok is True

    def test_all_three_checks_present_when_tier_passes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When tier passes, both canonical-API and oracle checks must always be run."""
        _write_config(tmp_path, "sos", "benchmarking")
        _build_engine(
            tmp_path / "benchmarks" / "sos" / "workspace" / "engine",
            {"game": "def create_game(): pass\n"},
        )
        _build_engine(
            tmp_path / "benchmarks" / "sos" / "data" / "test_oracle_workspace" / "engine",
            {"game": "def create_game(): pass\ndef oracle_only_fn(): pass\n"},
        )

        candidate = _write_candidate(tmp_path, "def test_it():\n    oracle_only_fn()\n")

        monkeypatch.setattr(
            _mod, "check_oracle_gate", lambda *a, **k: (True, "mock pass")
        )

        result = check_promotion_candidate(candidate, "sos_1", tmp_path, bench="sos")

        check_names = [c.name for c in result.checks]
        assert "tier" in check_names
        assert "canonical_api" in check_names
        assert "oracle_gate" in check_names
        assert len(result.checks) == 3


# ---------------------------------------------------------------------------
# Gap 4: main() prints each failing check's reason and the ADR-011 note to stderr
# ---------------------------------------------------------------------------


class TestMainOutputAndStderr:
    """main() must surface per-check reasons and the maintainer ADR-011 note."""

    def test_main_prints_adr011_note_to_stderr(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """The maintainer ADR-011 note must appear on stderr regardless of outcome."""
        _write_config(tmp_path, "sos", "benchmarking")
        _build_engine(
            tmp_path / "benchmarks" / "sos" / "workspace" / "engine",
            {"game": "def create_game(): pass\n"},
        )
        _build_engine(
            tmp_path / "benchmarks" / "sos" / "data" / "test_oracle_workspace" / "engine",
            {"game": "def create_game(): pass\n"},
        )

        candidate = _write_candidate(tmp_path, "def test_x(): pass\n")
        monkeypatch.setattr(
            _mod, "check_oracle_gate", lambda *a, **k: (True, "mock pass")
        )

        with mock.patch(
            "sys.argv",
            ["check_promotion_candidate.py", str(candidate), "--card", "sos_1"],
        ):
            with pytest.raises(SystemExit):
                main(repo_root=tmp_path)

        captured = capsys.readouterr()
        # ADR-011 maintainer note must be on stderr
        assert "ADR-011" in captured.err, (
            f"Expected ADR-011 mention in stderr; got: {captured.err!r}"
        )
        assert "SEPARATE concern" in captured.err or "separate" in captured.err.lower(), (
            f"Expected maintainer note text in stderr; got: {captured.err!r}"
        )

    def test_main_prints_fail_reason_for_each_failing_check(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """When a check fails, main() must print the check name and reason to stdout."""
        _write_config(tmp_path, "sos", "benchmarking")
        _build_engine(
            tmp_path / "benchmarks" / "sos" / "workspace" / "engine",
            {"game": "def create_game(): pass\n"},
        )
        _build_engine(
            tmp_path / "benchmarks" / "sos" / "data" / "test_oracle_workspace" / "engine",
            {"game": "def create_game(): pass\ndef oracle_only_fn(): pass\n"},
        )

        candidate = _write_candidate(tmp_path, "def test_it():\n    oracle_only_fn()\n")

        monkeypatch.setattr(
            _mod, "check_oracle_gate", lambda *a, **k: (True, "mock pass")
        )

        with mock.patch(
            "sys.argv",
            ["check_promotion_candidate.py", str(candidate), "--card", "sos_1"],
        ):
            with pytest.raises(SystemExit) as exc_info:
                main(repo_root=tmp_path)

        assert exc_info.value.code != 0

        captured = capsys.readouterr()
        stdout = captured.out

        # Must print the canonical_api check result with FAIL label
        assert "canonical_api" in stdout, (
            f"Expected 'canonical_api' in stdout; got: {stdout!r}"
        )
        assert "FAIL" in stdout, (
            f"Expected 'FAIL' label in stdout for failing check; got: {stdout!r}"
        )
        # Must mention the oracle-only symbol in the reason
        assert "oracle_only_fn" in stdout, (
            f"Expected oracle-only symbol name in stdout reason; got: {stdout!r}"
        )

    def test_main_prints_verdict_rejected_on_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """main() must print REJECTED verdict when any check fails."""
        _write_config(tmp_path, "sos", "released")
        candidate = _write_candidate(tmp_path, "def test_x(): pass\n")
        monkeypatch.setattr(
            _mod, "check_oracle_gate", lambda *a, **k: (False, "should not run")
        )

        with mock.patch(
            "sys.argv",
            ["check_promotion_candidate.py", str(candidate), "--card", "sos_1"],
        ):
            with pytest.raises(SystemExit) as exc_info:
                main(repo_root=tmp_path)

        assert exc_info.value.code != 0
        captured = capsys.readouterr()
        assert "REJECTED" in captured.out, (
            f"Expected REJECTED in stdout; got: {captured.out!r}"
        )


# ---------------------------------------------------------------------------
# Gap 5: Exit code is non-zero when ONLY the canonical-API check fails
# ---------------------------------------------------------------------------


class TestExitCodeCanonicalFailOnly:
    """Non-zero exit specifically when only the canonical-API check fails."""

    def test_exit_nonzero_only_canonical_api_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """tier=pass, canonical_api=fail, oracle=pass → exit code must be non-zero."""
        _write_config(tmp_path, "sos", "benchmarking")
        _build_engine(
            tmp_path / "benchmarks" / "sos" / "workspace" / "engine",
            {"game": "def create_game(): pass\n"},
        )
        _build_engine(
            tmp_path / "benchmarks" / "sos" / "data" / "test_oracle_workspace" / "engine",
            {"game": "def create_game(): pass\ndef oracle_only_fn(): pass\n"},
        )

        candidate = _write_candidate(tmp_path, "def test_it():\n    oracle_only_fn()\n")
        monkeypatch.setattr(
            _mod, "check_oracle_gate", lambda *a, **k: (True, "mock pass")
        )

        with mock.patch(
            "sys.argv",
            ["check_promotion_candidate.py", str(candidate), "--card", "sos_1"],
        ):
            with pytest.raises(SystemExit) as exc_info:
                main(repo_root=tmp_path)

        assert exc_info.value.code != 0, (
            "Exit code must be non-zero when only canonical-API check fails"
        )
        # Specifically should be 1
        assert exc_info.value.code == 1, (
            f"Expected exit code 1, got {exc_info.value.code}"
        )

    def test_exit_nonzero_only_oracle_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """tier=pass, canonical_api=pass, oracle=fail → exit code must be non-zero."""
        _write_config(tmp_path, "sos", "benchmarking")
        _build_engine(
            tmp_path / "benchmarks" / "sos" / "workspace" / "engine",
            {"game": "def create_game(): pass\n"},
        )
        _build_engine(
            tmp_path / "benchmarks" / "sos" / "data" / "test_oracle_workspace" / "engine",
            {"game": "def create_game(): pass\n"},
        )

        candidate = _write_candidate(tmp_path, "def test_it():\n    create_game()\n")
        monkeypatch.setattr(
            _mod, "check_oracle_gate", lambda *a, **k: (False, "mock oracle fail")
        )

        with mock.patch(
            "sys.argv",
            ["check_promotion_candidate.py", str(candidate), "--card", "sos_1"],
        ):
            with pytest.raises(SystemExit) as exc_info:
                main(repo_root=tmp_path)

        assert exc_info.value.code != 0, (
            "Exit code must be non-zero when only oracle check fails"
        )
        assert exc_info.value.code == 1
