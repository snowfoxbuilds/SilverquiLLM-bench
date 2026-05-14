"""Audited tests for Efflorescence (collector key 144).

Verifies the Efflorescence card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import Efflorescence

from engine.card import Instant
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestEfflorescenceBasicProperties:
    """Basic property tests for Efflorescence."""

    def test_is_instant(self) -> None:
        """Efflorescence must be a Instant subclass."""
        card = Efflorescence(name="Efflorescence", owner=None)
        assert isinstance(card, Instant)

    def test_name(self) -> None:
        """Efflorescence.name must be 'Efflorescence'."""
        card = Efflorescence(name="Efflorescence", owner=None)
        assert card.name == "Efflorescence"

    def test_card_types(self) -> None:
        """Efflorescence must have correct card types."""
        card = Efflorescence(name="Efflorescence", owner=None)
        assert CardType.INSTANT in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Efflorescence must have converted mana cost 3."""
        card = Efflorescence(name="Efflorescence", owner=None)
        assert card.mana_cost.cmc == 3

    def test_colors(self) -> None:
        """Efflorescence must have correct colors."""
        card = Efflorescence(name="Efflorescence", owner=None)
        assert "G" in card.colors


@pytest.mark.ability
class TestEfflorescenceAbilities:
    """Ability tests for Efflorescence — expected to fail against stubs."""

    def test_adds_plus_counter(self) -> None:
        """Resolution should add +1/+1 counter to target."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        target = Creature(name="Target", owner=player, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[target])
        card = Efflorescence(name="Efflorescence", owner=player)
        card.controller = player
        card._targets = [target]
        if hasattr(card, "set_targets"):
            card.set_targets([target])
        power_before = target.base_power
        card.on_resolve(game)
        power_after = target.power if hasattr(target, "power") else target.base_power
        assert power_after > power_before, (
            f"+1/+1 counter: power {power_before} -> {power_after}"
        )

    def test_grants_trample(self) -> None:
        """Resolution should grant trample."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Keyword
        game = create_game()
        player = game.players[0]
        target = Creature(name="KWTarget", owner=player, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[target])
        card = Efflorescence(name="Efflorescence", owner=player)
        card.controller = player
        card._targets = [target]
        if hasattr(card, "set_targets"):
            card.set_targets([target])
        card.on_resolve(game)
        assert Keyword.TRAMPLE in target.keywords, (
            "Target should have trample after resolution"
        )

    def test_gains_life(self) -> None:
        """Resolution should gain life."""
        from tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = Efflorescence(name="Efflorescence", owner=player)
        card.controller = player
        life_before = player.life
        card.on_resolve(game)
        assert player.life > life_before, (
            f"Should gain life: {life_before} -> {player.life}"
        )


@pytest.mark.edge
class TestEfflorescenceEdgeCases:
    """Edge case tests for Efflorescence."""

    def test_spell_resolution_on_empty_board(self) -> None:
        """Spell should handle resolution when no valid targets exist."""
        from tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = Efflorescence(name="Efflorescence", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass  # Expected if targets required
        # Should not raise TypeError/AttributeError
        assert True


@pytest.mark.interaction
class TestEfflorescenceInteractions:
    """Interaction tests for Efflorescence."""

    def test_get_targets_finds_creatures(self) -> None:
        """get_targets should return valid creature targets."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        creature = Creature(name="Target", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[creature])
        card = Efflorescence(name="Efflorescence", owner=player)
        card.controller = player
        targets = card.get_targets(game)
        assert len(targets) > 0, "Should find creature target"

    def test_does_not_affect_non_targets(self) -> None:
        """Resolution should not affect non-targeted permanents."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        own = Creature(name="Own", owner=player, base_power=4, base_toughness=4)
        set_board_state(game, 0, battlefield=[own])
        card = Efflorescence(name="Efflorescence", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
