"""Audited tests for Crackle with Power (collector key soa_42).

Verifies the Crackle with Power card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import CrackleWithPower

from engine.card import Sorcery
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestCrackleWithPowerBasicProperties:
    """Basic property tests for Crackle with Power."""

    def test_is_sorcery(self) -> None:
        """Crackle with Power must be a Sorcery subclass."""
        card = CrackleWithPower(name="Crackle with Power", owner=None)
        assert isinstance(card, Sorcery)

    def test_name(self) -> None:
        """CrackleWithPower.name must be 'Crackle with Power'."""
        card = CrackleWithPower(name="Crackle with Power", owner=None)
        assert card.name == "Crackle with Power"

    def test_card_types(self) -> None:
        """Crackle with Power must have correct card types."""
        card = CrackleWithPower(name="Crackle with Power", owner=None)
        assert CardType.SORCERY in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Crackle with Power must have converted mana cost 2."""
        card = CrackleWithPower(name="Crackle with Power", owner=None)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Crackle with Power must have correct colors."""
        card = CrackleWithPower(name="Crackle with Power", owner=None)
        assert "R" in card.colors


@pytest.mark.ability
class TestCrackleWithPowerAbilities:
    """Ability tests for Crackle with Power — expected to fail against stubs."""

    def test_on_resolve_changes_state(self) -> None:
        """Resolution must produce observable state change."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        target = Creature(name="Target", owner=opponent, base_power=2, base_toughness=2)
        set_board_state(game, 1, battlefield=[target])
        card = CrackleWithPower(name="Crackle with Power", owner=player)
        card.controller = player
        p_life = player.life
        o_life = opponent.life
        p_bf = len(game.get_battlefield(player).get_all())
        o_bf = len(game.get_battlefield(opponent).get_all())
        p_hand = len(player.zones[Zone.HAND].get_all())
        card.on_resolve(game)
        changed = (
            player.life != p_life or opponent.life != o_life or
            len(game.get_battlefield(player).get_all()) != p_bf or
            len(game.get_battlefield(opponent).get_all()) != o_bf or
            len(player.zones[Zone.HAND].get_all()) != p_hand or
            len(player.zones[Zone.GRAVEYARD].get_all()) > 0 or
            len(opponent.zones[Zone.GRAVEYARD].get_all()) > 0
        )
        assert changed, "on_resolve must change game state"


@pytest.mark.edge
class TestCrackleWithPowerEdgeCases:
    """Edge case tests for Crackle with Power."""

    def test_spell_resolution_on_empty_board(self) -> None:
        """Spell should handle resolution when no valid targets exist."""
        from benchmarks.sos.workspace.tests.test_utils import create_game
        game = create_game()
        player = game.players[0]
        card = CrackleWithPower(name="Crackle with Power", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass  # Expected if targets required
        # Should not raise TypeError/AttributeError
        assert True


@pytest.mark.interaction
class TestCrackleWithPowerInteractions:
    """Interaction tests for Crackle with Power."""

    def test_resolution_with_board_state(self) -> None:
        """Card should resolve correctly with established board."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        t1 = Creature(name="T1", owner=opponent, base_power=2, base_toughness=2)
        t2 = Creature(name="T2", owner=opponent, base_power=3, base_toughness=3)
        set_board_state(game, 1, battlefield=[t1, t2])
        card = CrackleWithPower(name="Crackle with Power", owner=player)
        card.controller = player
        card._targets = [t1]
        if hasattr(card, "set_targets"):
            card.set_targets([t1])
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Non-targeted creature should remain
        bf = game.get_battlefield(opponent).get_all()
        assert t2 in bf, "Non-targeted creature should remain"

    def test_does_not_affect_non_targets(self) -> None:
        """Resolution should not affect non-targeted permanents."""
        from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        own = Creature(name="Own", owner=player, base_power=4, base_toughness=4)
        set_board_state(game, 0, battlefield=[own])
        card = CrackleWithPower(name="Crackle with Power", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        # Own untargeted creature should remain
        bf = game.get_battlefield(player).get_all()
        assert own in bf, "Own untargeted creature should remain"
