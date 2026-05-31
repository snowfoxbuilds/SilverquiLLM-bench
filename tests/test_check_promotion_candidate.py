"""Tests for scripts/check_promotion_candidate.py — discovery→promotion bar gate.

Validates the three-check promotion gate:
1. Tier lock (beta/benchmarking allowed, released refused, fail-closed on missing)
2. Canonical-API check (reject oracle-only engine symbols)
3. Oracle gate (monkeypatched — never runs a real subprocess in these tests)
4. Orchestrator (check_promotion_candidate) short-circuits on tier failure
5. CLI (main) exit codes
6. Never-promotes invariant (no files written to audited tree)
7. Real benchmarks/sos/config.json exists with tier=benchmarking
"""

from __future__ import annotations

import importlib.util
import json
import sys
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
sys.modules["check_promotion_candidate"] = _mod
_spec.loader.exec_module(_mod)

check_tier = _mod.check_tier
check_canonical_api = _mod.check_canonical_api
check_oracle_gate = _mod.check_oracle_gate
check_promotion_candidate = _mod.check_promotion_candidate
main = _mod.main
CheckResult = _mod.CheckResult
PromotionResult = _mod.PromotionResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_config(root: Path, bench: str, tier: str) -> None:
    """Write benchmarks/<bench>/config.json with a given tier."""
    cfg_dir = root / "benchmarks" / bench
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "config.json").write_text(json.dumps({"tier": tier}))


def _write_candidate(root: Path, content: str, name: str = "test_candidate.py") -> Path:
    """Write a candidate test file and return its path."""
    candidate = root / name
    candidate.write_text(content)
    return candidate


def _build_engine(engine_dir: Path, symbols: dict[str, str]) -> None:
    """Build a minimal engine dir with a .py file exposing given symbols.

    symbols: mapping of module_name -> python source defining public symbols.
    """
    engine_dir.mkdir(parents=True, exist_ok=True)
    for mod_name, source in symbols.items():
        (engine_dir / f"{mod_name}.py").write_text(source)


# ---------------------------------------------------------------------------
# 1. Allowed path: Benchmarking + oracle PASS + canonical-only symbols
# ---------------------------------------------------------------------------


class TestAllowedPath:
    """Full allowed path: benchmarking tier, oracle passes, canonical API only."""

    def test_promotion_allowed_all_checks_pass(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_config(tmp_path, "sos", "benchmarking")

        # Canonical engine exposes create_game; oracle also exposes create_game
        canonical_src = "def create_game(): pass\n"
        _build_engine(
            tmp_path / "benchmarks" / "sos" / "workspace" / "engine",
            {"game": canonical_src},
        )
        _build_engine(
            tmp_path / "benchmarks" / "sos" / "data" / "test_oracle_workspace" / "engine",
            {"game": canonical_src},
        )

        candidate = _write_candidate(
            tmp_path,
            "from engine import game\ndef test_x(): game.create_game()\n",
        )

        # Mock oracle gate to pass
        monkeypatch.setattr(
            _mod, "check_oracle_gate", lambda *a, **k: (True, "mock pass")
        )

        result = check_promotion_candidate(candidate, "sos_1", tmp_path, bench="sos")

        assert result.allowed is True
        assert len(result.checks) == 3
        assert all(c.ok for c in result.checks)

    def test_main_exits_zero_on_allowed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_config(tmp_path, "sos", "benchmarking")
        canonical_src = "def create_game(): pass\n"
        _build_engine(
            tmp_path / "benchmarks" / "sos" / "workspace" / "engine",
            {"game": canonical_src},
        )
        _build_engine(
            tmp_path / "benchmarks" / "sos" / "data" / "test_oracle_workspace" / "engine",
            {"game": canonical_src},
        )

        candidate = _write_candidate(
            tmp_path,
            "from engine import game\ndef test_x(): game.create_game()\n",
        )

        monkeypatch.setattr(
            _mod, "check_oracle_gate", lambda *a, **k: (True, "mock pass")
        )

        with mock.patch(
            "sys.argv",
            ["check_promotion_candidate.py", str(candidate), "--card", "sos_1"],
        ):
            with pytest.raises(SystemExit) as exc_info:
                main(repo_root=tmp_path)
            assert exc_info.value.code == 0


# ---------------------------------------------------------------------------
# 2. Oracle reject
# ---------------------------------------------------------------------------


class TestOracleReject:
    """Oracle gate fails → promotion rejected."""

    def test_oracle_fail_rejects_candidate(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_config(tmp_path, "sos", "benchmarking")
        canonical_src = "def create_game(): pass\n"
        _build_engine(
            tmp_path / "benchmarks" / "sos" / "workspace" / "engine",
            {"game": canonical_src},
        )
        _build_engine(
            tmp_path / "benchmarks" / "sos" / "data" / "test_oracle_workspace" / "engine",
            {"game": canonical_src},
        )

        candidate = _write_candidate(
            tmp_path,
            "def test_x(): pass\n",
        )

        oracle_reason = "Candidate FAILED against oracle (exit 1)"
        monkeypatch.setattr(
            _mod, "check_oracle_gate", lambda *a, **k: (False, oracle_reason)
        )

        result = check_promotion_candidate(candidate, "sos_1", tmp_path, bench="sos")

        assert result.allowed is False
        # Oracle check reason is surfaced in the checks list
        oracle_checks = [c for c in result.checks if c.name == "oracle_gate"]
        assert len(oracle_checks) == 1
        assert oracle_checks[0].ok is False
        assert oracle_reason in oracle_checks[0].reason

    def test_main_exits_nonzero_on_oracle_fail(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_config(tmp_path, "sos", "benchmarking")
        canonical_src = "def create_game(): pass\n"
        _build_engine(
            tmp_path / "benchmarks" / "sos" / "workspace" / "engine",
            {"game": canonical_src},
        )
        _build_engine(
            tmp_path / "benchmarks" / "sos" / "data" / "test_oracle_workspace" / "engine",
            {"game": canonical_src},
        )

        candidate = _write_candidate(tmp_path, "def test_x(): pass\n")

        monkeypatch.setattr(
            _mod, "check_oracle_gate", lambda *a, **k: (False, "mock fail")
        )

        with mock.patch(
            "sys.argv",
            ["check_promotion_candidate.py", str(candidate), "--card", "sos_1"],
        ):
            with pytest.raises(SystemExit) as exc_info:
                main(repo_root=tmp_path)
            assert exc_info.value.code != 0


# ---------------------------------------------------------------------------
# 3. Released tier refusal + case-insensitivity + short-circuit
# ---------------------------------------------------------------------------


class TestReleasedRefusal:
    """Released tier → rejected; oracle gate must NOT be called."""

    def test_released_tier_rejects(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_config(tmp_path, "sos", "released")

        candidate = _write_candidate(tmp_path, "def test_x(): pass\n")

        # If oracle gate is called, raise to fail the test
        def _oracle_should_not_run(*a, **k):
            raise AssertionError("oracle gate should NOT be called for released tier")

        monkeypatch.setattr(_mod, "check_oracle_gate", _oracle_should_not_run)

        result = check_promotion_candidate(candidate, "sos_1", tmp_path, bench="sos")

        assert result.allowed is False
        # Only tier check should be present (short-circuit)
        assert len(result.checks) == 1
        assert result.checks[0].name == "tier"
        assert result.checks[0].ok is False

    def test_released_case_insensitive_uppercase(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_config(tmp_path, "sos", "Released")

        candidate = _write_candidate(tmp_path, "def test_x(): pass\n")

        monkeypatch.setattr(
            _mod,
            "check_oracle_gate",
            lambda *a, **k: (_ for _ in ()).throw(
                AssertionError("oracle must not run")
            ),
        )

        result = check_promotion_candidate(candidate, "sos_1", tmp_path, bench="sos")
        assert result.allowed is False

    def test_benchmarking_case_insensitive(self, tmp_path: Path) -> None:
        _write_config(tmp_path, "sos", "BENCHMARKING")
        ok, reason = check_tier(tmp_path, bench="sos")
        assert ok is True

    def test_main_exits_nonzero_on_released(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_config(tmp_path, "sos", "released")
        candidate = _write_candidate(tmp_path, "def test_x(): pass\n")

        monkeypatch.setattr(
            _mod,
            "check_oracle_gate",
            lambda *a, **k: (_ for _ in ()).throw(
                AssertionError("oracle must not run")
            ),
        )

        with mock.patch(
            "sys.argv",
            ["check_promotion_candidate.py", str(candidate), "--card", "sos_1"],
        ):
            with pytest.raises(SystemExit) as exc_info:
                main(repo_root=tmp_path)
            assert exc_info.value.code != 0


# ---------------------------------------------------------------------------
# 4. check_tier directly
# ---------------------------------------------------------------------------


class TestCheckTier:
    """Unit tests for check_tier covering all tier values and error paths."""

    def test_beta_allowed(self, tmp_path: Path) -> None:
        _write_config(tmp_path, "sos", "beta")
        ok, reason = check_tier(tmp_path, bench="sos")
        assert ok is True

    def test_benchmarking_allowed(self, tmp_path: Path) -> None:
        _write_config(tmp_path, "sos", "benchmarking")
        ok, reason = check_tier(tmp_path, bench="sos")
        assert ok is True

    def test_released_not_allowed(self, tmp_path: Path) -> None:
        _write_config(tmp_path, "sos", "released")
        ok, reason = check_tier(tmp_path, bench="sos")
        assert ok is False
        assert "released" in reason.lower() or "does not allow" in reason.lower()

    def test_missing_config_fail_closed(self, tmp_path: Path) -> None:
        # No config.json at all
        ok, reason = check_tier(tmp_path, bench="sos")
        assert ok is False
        assert "fail-closed" in reason.lower() or "not found" in reason.lower()

    def test_missing_tier_key_fail_closed(self, tmp_path: Path) -> None:
        cfg_dir = tmp_path / "benchmarks" / "sos"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        (cfg_dir / "config.json").write_text(json.dumps({"version": 1}))
        ok, reason = check_tier(tmp_path, bench="sos")
        assert ok is False
        assert "tier" in reason.lower()

    def test_case_insensitive_beta(self, tmp_path: Path) -> None:
        _write_config(tmp_path, "sos", "Beta")
        ok, _ = check_tier(tmp_path, bench="sos")
        assert ok is True

    def test_invalid_json_fail_closed(self, tmp_path: Path) -> None:
        cfg_dir = tmp_path / "benchmarks" / "sos"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        (cfg_dir / "config.json").write_text("not json{{{")
        ok, reason = check_tier(tmp_path, bench="sos")
        assert ok is False
        assert "fail-closed" in reason.lower()


# ---------------------------------------------------------------------------
# 5. check_canonical_api directly (REAL, not mocked)
# ---------------------------------------------------------------------------


class TestCheckCanonicalApi:
    """Real AST-based canonical API check with fixture engine dirs."""

    def test_canonical_only_symbol_passes(self, tmp_path: Path) -> None:
        """Candidate uses symbol X which is in both engines → ok."""
        _build_engine(
            tmp_path / "benchmarks" / "sos" / "workspace" / "engine",
            {"game": "def create_game(): pass\nclass Game: pass\n"},
        )
        _build_engine(
            tmp_path / "benchmarks" / "sos" / "data" / "test_oracle_workspace" / "engine",
            {"game": "def create_game(): pass\nclass Game: pass\n"},
        )

        candidate = _write_candidate(
            tmp_path,
            "def test_it():\n    g = Game()\n    create_game()\n",
        )

        ok, reason = check_canonical_api(candidate, tmp_path, bench="sos")
        assert ok is True

    def test_oracle_only_symbol_rejected(self, tmp_path: Path) -> None:
        """Candidate uses symbol Y which is in oracle engine but NOT canonical → rejected."""
        _build_engine(
            tmp_path / "benchmarks" / "sos" / "workspace" / "engine",
            {"game": "def create_game(): pass\n"},
        )
        _build_engine(
            tmp_path / "benchmarks" / "sos" / "data" / "test_oracle_workspace" / "engine",
            {"game": "def create_game(): pass\ndef oracle_only_helper(): pass\n"},
        )

        candidate = _write_candidate(
            tmp_path,
            "def test_it():\n    oracle_only_helper()\n",
        )

        ok, reason = check_canonical_api(candidate, tmp_path, bench="sos")
        assert ok is False
        assert "oracle_only_helper" in reason

    def test_stdlib_pytest_only_passes(self, tmp_path: Path) -> None:
        """Candidate using only stdlib/pytest (no engine symbols) → ok."""
        _build_engine(
            tmp_path / "benchmarks" / "sos" / "workspace" / "engine",
            {"game": "def create_game(): pass\n"},
        )
        _build_engine(
            tmp_path / "benchmarks" / "sos" / "data" / "test_oracle_workspace" / "engine",
            {"game": "def create_game(): pass\n"},
        )

        candidate = _write_candidate(
            tmp_path,
            "import pytest\ndef test_it():\n    assert True\n    len([1,2])\n",
        )

        ok, reason = check_canonical_api(candidate, tmp_path, bench="sos")
        assert ok is True

    def test_oracle_only_module_name_rejected(self, tmp_path: Path) -> None:
        """Oracle engine has a module 'extra_utils' not in canonical → rejected when referenced."""
        _build_engine(
            tmp_path / "benchmarks" / "sos" / "workspace" / "engine",
            {"game": "def create_game(): pass\n"},
        )
        _build_engine(
            tmp_path / "benchmarks" / "sos" / "data" / "test_oracle_workspace" / "engine",
            {
                "game": "def create_game(): pass\n",
                "extra_utils": "def helper(): pass\n",
            },
        )

        # Candidate calls extra_utils.helper() — extra_utils is a module name AND helper a fn
        # The module name "extra_utils" is oracle-only
        candidate = _write_candidate(
            tmp_path,
            "import extra_utils\ndef test_it():\n    extra_utils.helper()\n",
        )

        ok, reason = check_canonical_api(candidate, tmp_path, bench="sos")
        assert ok is False
        # Should name at least one offending symbol
        assert "extra_utils" in reason or "helper" in reason

    def test_empty_engines_passes(self, tmp_path: Path) -> None:
        """Both engine dirs empty/missing → no symbols to violate → ok."""
        (tmp_path / "benchmarks" / "sos" / "workspace" / "engine").mkdir(parents=True)
        (tmp_path / "benchmarks" / "sos" / "data" / "test_oracle_workspace" / "engine").mkdir(parents=True)

        candidate = _write_candidate(
            tmp_path,
            "def test_it():\n    pass\n",
        )

        ok, reason = check_canonical_api(candidate, tmp_path, bench="sos")
        assert ok is True


# ---------------------------------------------------------------------------
# 5b. Canonical-API check — attribute/method/property granularity
#     (regression guard for the oracle-only-primitive blind spot)
# ---------------------------------------------------------------------------


class TestCanonicalApiAttributeGranularity:
    """The canonical-API check must catch oracle-only symbols that live *inside*
    a class — dataclass fields, properties/methods, and instance attributes —
    not just module/class/function names. These are the exact primitives the
    Phase 18 cleanup added only to the oracle engine (mana_spent,
    restricted_mana, rng)."""

    def test_oracle_only_dataclass_field_rejected(self, tmp_path: Path) -> None:
        """A class-body field present only in the oracle engine → rejected.

        Mirrors ``StackObject.mana_spent`` (``mana_spent: int = 0``).
        """
        _build_engine(
            tmp_path / "benchmarks" / "sos" / "workspace" / "engine",
            {"stack": "class StackObject:\n    pass\n"},
        )
        _build_engine(
            tmp_path / "benchmarks" / "sos" / "data" / "test_oracle_workspace" / "engine",
            {"stack": "class StackObject:\n    mana_spent: int = 0\n"},
        )

        candidate = _write_candidate(
            tmp_path,
            "def test_it():\n    obj = StackObject()\n    assert obj.mana_spent == 0\n",
        )

        ok, reason = check_canonical_api(candidate, tmp_path, bench="sos")
        assert ok is False
        assert "mana_spent" in reason

    def test_oracle_only_property_rejected(self, tmp_path: Path) -> None:
        """A property/method present only in the oracle engine → rejected.

        Mirrors ``ManaPool.restricted_mana`` (an ``@property``).
        """
        _build_engine(
            tmp_path / "benchmarks" / "sos" / "workspace" / "engine",
            {"mana": "class ManaPool:\n    pass\n"},
        )
        _build_engine(
            tmp_path / "benchmarks" / "sos" / "data" / "test_oracle_workspace" / "engine",
            {
                "mana": (
                    "class ManaPool:\n"
                    "    @property\n"
                    "    def restricted_mana(self):\n"
                    "        return []\n"
                )
            },
        )

        candidate = _write_candidate(
            tmp_path,
            "def test_it():\n    p = ManaPool()\n    assert p.restricted_mana == []\n",
        )

        ok, reason = check_canonical_api(candidate, tmp_path, bench="sos")
        assert ok is False
        assert "restricted_mana" in reason

    def test_oracle_only_instance_attribute_rejected(self, tmp_path: Path) -> None:
        """An instance attribute (``self.x = ...``) only in the oracle engine → rejected.

        Mirrors ``game.rng`` (``self.rng = random.Random()``).
        """
        _build_engine(
            tmp_path / "benchmarks" / "sos" / "workspace" / "engine",
            {
                "game_state": (
                    "class GameState:\n"
                    "    def __init__(self):\n"
                    "        self.seed = 0\n"
                )
            },
        )
        _build_engine(
            tmp_path / "benchmarks" / "sos" / "data" / "test_oracle_workspace" / "engine",
            {
                "game_state": (
                    "import random\n"
                    "class GameState:\n"
                    "    def __init__(self):\n"
                    "        self.seed = 0\n"
                    "        self.rng = random.Random()\n"
                )
            },
        )

        candidate = _write_candidate(
            tmp_path,
            "def test_it():\n    g = GameState()\n    g.rng.random()\n",
        )

        ok, reason = check_canonical_api(candidate, tmp_path, bench="sos")
        assert ok is False
        assert "rng" in reason

    def test_shared_attribute_passes(self, tmp_path: Path) -> None:
        """An attribute present in BOTH engines must NOT be a false positive."""
        shared = "class StackObject:\n    mana_spent: int = 0\n"
        _build_engine(
            tmp_path / "benchmarks" / "sos" / "workspace" / "engine",
            {"stack": shared},
        )
        _build_engine(
            tmp_path / "benchmarks" / "sos" / "data" / "test_oracle_workspace" / "engine",
            {"stack": shared},
        )

        candidate = _write_candidate(
            tmp_path,
            "def test_it():\n    obj = StackObject()\n    assert obj.mana_spent == 0\n",
        )

        ok, reason = check_canonical_api(candidate, tmp_path, bench="sos")
        assert ok is True

    def test_oracle_only_symbol_in_subpackage_rejected(self, tmp_path: Path) -> None:
        """rglob: an oracle-only symbol in an engine SUBPACKAGE is still seen.

        With the old non-recursive ``glob("*.py")`` this symbol would be invisible
        and the candidate would wrongly pass.
        """
        # Canonical engine: flat, no subpackage
        _build_engine(
            tmp_path / "benchmarks" / "sos" / "workspace" / "engine",
            {"game": "def create_game(): pass\n"},
        )
        # Oracle engine: defines deep_helper inside a subpackage
        oracle_engine = (
            tmp_path / "benchmarks" / "sos" / "data" / "test_oracle_workspace" / "engine"
        )
        _build_engine(oracle_engine, {"game": "def create_game(): pass\n"})
        sub = oracle_engine / "sub"
        sub.mkdir(parents=True)
        (sub / "__init__.py").write_text("")
        (sub / "extra.py").write_text("def deep_helper(): pass\n")

        candidate = _write_candidate(
            tmp_path,
            "def test_it():\n    deep_helper()\n",
        )

        ok, reason = check_canonical_api(candidate, tmp_path, bench="sos")
        assert ok is False
        assert "deep_helper" in reason


# ---------------------------------------------------------------------------
# 6. Fail-closed oracle gate
# ---------------------------------------------------------------------------


class TestOracleGateFailClosed:
    """Oracle gate returns not-ok on missing oracle card / subprocess errors."""

    def test_missing_oracle_card_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Monkeypatch check_oracle_gate to simulate missing oracle card return."""
        monkeypatch.setattr(
            _mod,
            "check_oracle_gate",
            lambda *a, **k: (False, "Oracle card_impl.py not found (fail-closed)"),
        )

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
        result = check_promotion_candidate(candidate, "sos_1", tmp_path, bench="sos")

        assert result.allowed is False
        oracle_checks = [c for c in result.checks if c.name == "oracle_gate"]
        assert len(oracle_checks) == 1
        assert oracle_checks[0].ok is False
        assert "fail-closed" in oracle_checks[0].reason.lower()

    def test_subprocess_error_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Monkeypatch check_oracle_gate to simulate subprocess error."""
        monkeypatch.setattr(
            _mod,
            "check_oracle_gate",
            lambda *a, **k: (False, "Oracle gate subprocess error: OSError (fail-closed)"),
        )

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
        result = check_promotion_candidate(candidate, "sos_1", tmp_path, bench="sos")

        assert result.allowed is False

    def test_real_oracle_gate_missing_card_fails(self, tmp_path: Path) -> None:
        """Call the REAL check_oracle_gate pointing at an empty oracle tree → fail-closed."""
        # Set up minimal dirs but no card_impl.py
        oracle_cards = tmp_path / "benchmarks" / "sos" / "data" / "test_oracle_workspace" / "cards" / "sos" / "sos_nonexistent"
        oracle_cards.mkdir(parents=True)
        # No card_impl.py in that dir

        candidate = _write_candidate(tmp_path, "def test_x(): pass\n")

        ok, reason = check_oracle_gate(candidate, "sos_nonexistent", tmp_path, bench="sos")
        assert ok is False
        assert "not found" in reason.lower() or "fail-closed" in reason.lower()


# ---------------------------------------------------------------------------
# 7. Never promotes: no files written to audited tree
# ---------------------------------------------------------------------------


class TestNeverPromotes:
    """check_promotion_candidate / main must NOT modify the audited tree."""

    def test_no_files_written_to_audited(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_config(tmp_path, "sos", "benchmarking")
        canonical_src = "def create_game(): pass\n"
        _build_engine(
            tmp_path / "benchmarks" / "sos" / "workspace" / "engine",
            {"game": canonical_src},
        )
        _build_engine(
            tmp_path / "benchmarks" / "sos" / "data" / "test_oracle_workspace" / "engine",
            {"game": canonical_src},
        )

        # Set up the audited directory with a known state
        audited_dir = tmp_path / "benchmarks" / "sos" / "data" / "tests" / "audited" / "sos"
        audited_dir.mkdir(parents=True)
        marker = audited_dir / "existing_test.py"
        marker.write_text("# existing\n")

        # Snapshot: record files before
        files_before = set(audited_dir.rglob("*"))

        candidate = _write_candidate(tmp_path, "def test_x(): pass\n")

        monkeypatch.setattr(
            _mod, "check_oracle_gate", lambda *a, **k: (True, "mock pass")
        )

        result = check_promotion_candidate(candidate, "sos_1", tmp_path, bench="sos")
        assert result.allowed is True

        # Verify no new files created
        files_after = set(audited_dir.rglob("*"))
        assert files_after == files_before, (
            f"New files created in audited dir: {files_after - files_before}"
        )
        # Verify marker file unchanged
        assert marker.read_text() == "# existing\n"

    def test_rejected_path_no_files_written_to_audited(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Even on rejection, nothing should be written to audited."""
        _write_config(tmp_path, "sos", "released")

        audited_dir = tmp_path / "benchmarks" / "sos" / "data" / "tests" / "audited" / "sos"
        audited_dir.mkdir(parents=True)
        files_before = set(audited_dir.rglob("*"))

        candidate = _write_candidate(tmp_path, "def test_x(): pass\n")

        monkeypatch.setattr(
            _mod,
            "check_oracle_gate",
            lambda *a, **k: (_ for _ in ()).throw(
                AssertionError("oracle must not run")
            ),
        )

        result = check_promotion_candidate(candidate, "sos_1", tmp_path, bench="sos")
        assert result.allowed is False

        files_after = set(audited_dir.rglob("*"))
        assert files_after == files_before


# ---------------------------------------------------------------------------
# 8. Real benchmarks/sos/config.json exists with tier=benchmarking
# ---------------------------------------------------------------------------


class TestRealConfig:
    """Verify the actual committed benchmarks/sos/config.json."""

    def test_config_json_exists(self) -> None:
        config_path = REPO_ROOT / "benchmarks" / "sos" / "config.json"
        assert config_path.is_file(), f"Expected {config_path} to exist"

    def test_config_json_parses_with_tier_benchmarking(self) -> None:
        config_path = REPO_ROOT / "benchmarks" / "sos" / "config.json"
        data = json.loads(config_path.read_text(encoding="utf-8"))
        assert "tier" in data
        assert data["tier"].lower() == "benchmarking"

    def test_check_tier_passes_on_real_repo(self) -> None:
        """check_tier with the real repo root returns ok."""
        ok, reason = check_tier(REPO_ROOT, bench="sos")
        assert ok is True


# ---------------------------------------------------------------------------
# Additional: PromotionResult and CheckResult dataclass structure
# ---------------------------------------------------------------------------


class TestDataclasses:
    """PromotionResult and CheckResult expose expected fields."""

    def test_promotion_result_fields(self) -> None:
        pr = PromotionResult(allowed=True, checks=[])
        assert pr.allowed is True
        assert pr.checks == []

    def test_check_result_fields(self) -> None:
        cr = CheckResult(name="tier", ok=True, reason="ok")
        assert cr.name == "tier"
        assert cr.ok is True
        assert cr.reason == "ok"

    def test_promotion_result_default_checks(self) -> None:
        pr = PromotionResult(allowed=False)
        assert isinstance(pr.checks, list)
        assert len(pr.checks) == 0
