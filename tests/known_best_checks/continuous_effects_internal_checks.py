"""Known-Best engine checks moved out of the Audited Engine Tests' test_continuous_effects.py:
they drive the engine directly or test its internals, in positions no
FDN card reaches through play, so they guard the Known-Best engine
without being graded against candidates (ADR-018)."""

from __future__ import annotations

import pytest
from engine.card import Creature
from engine.continuous_effects import (
    DURATION_END_OF_TURN,
    DURATION_PERMANENT,
    ContinuousEffect,
    EffectManager,
    Layer,
)
from engine.game_state import GameState
from test_utils import DeterministicPlayer

# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def players() -> list[DeterministicPlayer]:
    """Create two DeterministicPlayers."""
    return [
        DeterministicPlayer("Alice"),
        DeterministicPlayer("Bob"),
    ]


@pytest.fixture()
def game(players: list[DeterministicPlayer]) -> GameState:
    """Create a GameState with two players."""
    return GameState(players)


@pytest.fixture()
def manager() -> EffectManager:
    """Create a fresh EffectManager."""
    return EffectManager()


def _make_creature(name: str = "Bear", power: int = 2, toughness: int = 2) -> Creature:
    """Create a simple creature with given stats."""
    return Creature(name=name, base_power=power, base_toughness=toughness)


# ---------------------------------------------------------------------------
# Layer enum
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# SubLayer enum
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# Duration constants
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# ContinuousEffect dataclass
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# EffectManager — add
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# EffectManager — remove
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# EffectManager — remove_expired
# ---------------------------------------------------------------------------


class TestEffectManagerRemoveExpired:
    """Verify EffectManager.remove_expired behaviour."""



    def test_turn_numbered_effect_not_expired_yet(self, manager: EffectManager, game: GameState):
        """Effect with duration=5 should remain when turn_number is 3."""
        game.turn_number = 3
        eff = ContinuousEffect(source="s", layer=Layer.TYPE, duration=5)
        manager.add(eff)
        removed = manager.remove_expired(game)
        assert removed == 0
        assert len(manager) == 1

    def test_turn_numbered_effect_expired(self, manager: EffectManager, game: GameState):
        """Effect with duration=3 should be removed when turn_number is 4."""
        game.turn_number = 4
        eff = ContinuousEffect(source="s", layer=Layer.TYPE, duration=3)
        manager.add(eff)
        removed = manager.remove_expired(game)
        assert removed == 1
        assert len(manager) == 0

    def test_turn_numbered_effect_exact_turn_stays(self, manager: EffectManager, game: GameState):
        """Effect with duration=3 should stay when turn_number is exactly 3."""
        game.turn_number = 3
        eff = ContinuousEffect(source="s", layer=Layer.TYPE, duration=3)
        manager.add(eff)
        removed = manager.remove_expired(game)
        assert removed == 0
        assert len(manager) == 1

    def test_mixed_batch_removal(self, manager: EffectManager, game: GameState):
        """Remove only expired effects from a mixed set."""
        game.turn_number = 5
        perm = ContinuousEffect(source="s", layer=Layer.TYPE, duration=DURATION_PERMANENT)
        eot = ContinuousEffect(source="s", layer=Layer.TYPE, duration=DURATION_END_OF_TURN)
        expired = ContinuousEffect(source="s", layer=Layer.TYPE, duration=3)
        still_active = ContinuousEffect(source="s", layer=Layer.TYPE, duration=10)
        manager.add(perm)
        manager.add(eot)
        manager.add(expired)
        manager.add(still_active)
        removed = manager.remove_expired(game)
        assert removed == 2
        assert len(manager) == 2




# ---------------------------------------------------------------------------
# EffectManager — apply_all
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# Layer 4 — Type-changing effects
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# Layer 6 — Ability granting/removing
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# Layer 7c — P/T modification (+N/+N effects)
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# Layer 7d — Counter-based P/T
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# Multi-layer ordering: type + ability + P/T on same creature
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# GameState integration
# ---------------------------------------------------------------------------




# ---------------------------------------------------------------------------
# Duration-based end-to-end scenarios
# ---------------------------------------------------------------------------


class TestDurationScenarios:
    """End-to-end tests for duration-based effect expiry."""


    def test_turn_numbered_effect_stays_until_expiry(self, manager: EffectManager, game: GameState):
        """Effect with duration=3 stays on turns 1-3, removed on turn 4."""
        eff = ContinuousEffect(source="s", layer=Layer.TYPE, duration=3)
        manager.add(eff)

        game.turn_number = 1
        assert manager.remove_expired(game) == 0

        game.turn_number = 3
        assert manager.remove_expired(game) == 0
        assert len(manager) == 1

        game.turn_number = 4
        assert manager.remove_expired(game) == 1
        assert len(manager) == 0

    def test_permanent_effect_survives_many_turns(self, manager: EffectManager, game: GameState):
        """Permanent effect is never removed by remove_expired."""
        eff = ContinuousEffect(source="s", layer=Layer.TYPE, duration=DURATION_PERMANENT)
        manager.add(eff)

        for turn in range(1, 20):
            game.turn_number = turn
            manager.remove_expired(game)

        assert len(manager) == 1
