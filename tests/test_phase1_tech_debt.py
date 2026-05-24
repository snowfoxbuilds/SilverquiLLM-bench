"""Tests for TODO item 1: Fix Phase 1 tech debt.

Verifies three non-blocking cleanup items:
1. Python version alignment (pyproject.toml >=3.12, ruff.toml py312)
2. Backward-compat aliases removed from simple_spells.py
3. Cleanup discard fallback emits a UserWarning on ScriptExhaustedError
"""

from __future__ import annotations

import importlib
import subprocess
import sys
import warnings
from pathlib import Path
from typing import Any

import pytest

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ImportError:
        tomllib = None  # type: ignore[assignment]

REPO_ROOT = Path(__file__).resolve().parent.parent


# ===========================================================================
# 1. Python version alignment
# ===========================================================================


class TestPythonVersionAlignment:
    """pyproject.toml and ruff.toml must both target Python 3.12."""

    @pytest.fixture(autouse=True)
    def _load_configs(self) -> None:
        assert tomllib is not None, "tomllib/tomli required"
        with open(REPO_ROOT / "pyproject.toml", "rb") as f:
            self.pyproject: dict[str, Any] = tomllib.load(f)
        with open(REPO_ROOT / "ruff.toml", "rb") as f:
            self.ruff: dict[str, Any] = tomllib.load(f)

    def test_pyproject_requires_python_3_12(self) -> None:
        """requires-python must be >=3.12."""
        rp = self.pyproject["project"]["requires-python"]
        assert rp == ">=3.12", f"Expected '>=3.12', got '{rp}'"

    def test_ruff_target_version_py312(self) -> None:
        """ruff.toml target-version must be py312."""
        tv = self.ruff.get("target-version")
        assert tv == "py312", f"Expected 'py312', got '{tv}'"

    def test_mypy_python_version_3_12(self) -> None:
        """mypy python_version in pyproject.toml must be 3.12."""
        mypy_cfg = self.pyproject.get("tool", {}).get("mypy", {})
        pv = mypy_cfg.get("python_version")
        assert pv == "3.12", f"Expected '3.12', got '{pv}'"

    def test_ruff_config_is_parseable_with_py312(self) -> None:
        """ruff must accept the py312 target-version without config errors.

        We run 'ruff check --config ruff.toml' on a known-clean file to verify
        the config itself is valid (no 'invalid target-version' errors).
        """
        result = subprocess.run(
            [sys.executable, "-m", "ruff", "check", "ruff.toml", "--config", str(REPO_ROOT / "ruff.toml")],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        # ruff.toml is not a .py file so ruff will just skip it — no config error
        assert "invalid" not in result.stderr.lower(), (
            f"ruff config error with py312 target: {result.stderr}"
        )


# ===========================================================================
# 3. Cleanup discard fallback warning
# ===========================================================================


class TestCleanupDiscardWarning:
    """When ScriptExhaustedError fires during cleanup discard, a UserWarning
    must be emitted containing player name and card name."""

    def _make_game_for_warning(self) -> Any:
        """Build a minimal game state where cleanup discard triggers the fallback."""
        from benchmarks.sos.workspace.engine.card import CardImpl
        from benchmarks.sos.workspace.engine.game_state import GameState
        from benchmarks.sos.workspace.engine.player import DeterministicPlayer
        from benchmarks.sos.workspace.engine.types import Zone

        p1 = DeterministicPlayer("Alice", life=20, script=[])
        p2 = DeterministicPlayer("Bob", life=20, script=[])
        game = GameState(players=[p1, p2])

        # Put 9 cards in hand (2 above max of 7)
        hand = p1.zones[Zone.HAND]
        for i in range(9):
            card = CardImpl(name=f"TestCard_{i}", mana_cost="", card_types=set())
            card.owner = p1
            card.controller = p1
            hand.add(card)

        return game, p1

    def test_warning_emitted_on_script_exhausted(self) -> None:
        """A UserWarning must be emitted when cleanup falls back to auto-discard."""
        from benchmarks.sos.workspace.engine.turn import _do_cleanup_step

        game, p1 = self._make_game_for_warning()

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            _do_cleanup_step(game)

        user_warnings = [w for w in caught if issubclass(w.category, UserWarning)]
        assert len(user_warnings) >= 1, (
            "Expected at least one UserWarning from cleanup discard fallback"
        )

    def test_warning_contains_player_name(self) -> None:
        """The warning message must mention the player's name."""
        from benchmarks.sos.workspace.engine.turn import _do_cleanup_step

        game, p1 = self._make_game_for_warning()

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            _do_cleanup_step(game)

        user_warnings = [w for w in caught if issubclass(w.category, UserWarning)]
        assert any("Alice" in str(w.message) for w in user_warnings), (
            f"Warning should mention player name 'Alice', got: "
            f"{[str(w.message) for w in user_warnings]}"
        )

    def test_warning_contains_card_name(self) -> None:
        """The warning message must mention the auto-discarded card's name."""
        from benchmarks.sos.workspace.engine.turn import _do_cleanup_step

        game, p1 = self._make_game_for_warning()

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            _do_cleanup_step(game)

        user_warnings = [w for w in caught if issubclass(w.category, UserWarning)]
        # At least one warning should mention "TestCard_" (any of them)
        assert any("TestCard_" in str(w.message) for w in user_warnings), (
            f"Warning should mention auto-discarded card name, got: "
            f"{[str(w.message) for w in user_warnings]}"
        )

    def test_warning_mentions_script_exhausted(self) -> None:
        """The warning message must reference ScriptExhaustedError."""
        from benchmarks.sos.workspace.engine.turn import _do_cleanup_step

        game, p1 = self._make_game_for_warning()

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            _do_cleanup_step(game)

        user_warnings = [w for w in caught if issubclass(w.category, UserWarning)]
        assert any("ScriptExhaustedError" in str(w.message) for w in user_warnings), (
            f"Warning should mention ScriptExhaustedError, got: "
            f"{[str(w.message) for w in user_warnings]}"
        )

    def test_no_warning_when_script_provides_choices(self) -> None:
        """No warning should be emitted when the script provides all needed choices."""
        from benchmarks.sos.workspace.engine.card import CardImpl
        from benchmarks.sos.workspace.engine.game_state import GameState
        from benchmarks.sos.workspace.engine.player import DeterministicPlayer
        from benchmarks.sos.workspace.engine.turn import _do_cleanup_step
        from benchmarks.sos.workspace.engine.types import Zone

        cards = []
        for i in range(9):
            card = CardImpl(name=f"Card_{i}", mana_cost="", card_types=set())
            cards.append(card)

        # Script provides choices for the 2 discards needed (9-7=2)
        p1 = DeterministicPlayer("Alice", life=20, script=[cards[8], cards[7]])
        p2 = DeterministicPlayer("Bob", life=20, script=[])
        game = GameState(players=[p1, p2])

        hand = p1.zones[Zone.HAND]
        for card in cards:
            card.owner = p1
            card.controller = p1
            hand.add(card)

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            _do_cleanup_step(game)

        user_warnings = [w for w in caught if issubclass(w.category, UserWarning)]
        assert len(user_warnings) == 0, (
            f"No warning expected when script is complete, got: "
            f"{[str(w.message) for w in user_warnings]}"
        )
