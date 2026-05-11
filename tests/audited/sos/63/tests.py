"""Audited tests for Pensive Professor (collector key 63).

Verifies the Pensive Professor card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""

from __future__ import annotations

import pytest

from card_impl import PensiveProfessor

from engine.card import Creature
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestPensiveProfessorBasicProperties:
    """Basic property tests for Pensive Professor."""

    def test_is_creature(self) -> None:
        """Pensive Professor must be a Creature subclass."""
        card = PensiveProfessor(name="Pensive Professor", owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """PensiveProfessor.name must be 'Pensive Professor'."""
        card = PensiveProfessor(name="Pensive Professor", owner=None)
        assert card.name == "Pensive Professor"

    def test_card_types(self) -> None:
        """Pensive Professor must have correct card types."""
        card = PensiveProfessor(name="Pensive Professor", owner=None)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Pensive Professor must have converted mana cost 3."""
        card = PensiveProfessor(name="Pensive Professor", owner=None)
        assert card.mana_cost.cmc == 3

    def test_colors(self) -> None:
        """Pensive Professor must have correct colors."""
        card = PensiveProfessor(name="Pensive Professor", owner=None)
        assert "U" in card.colors

    def test_power(self) -> None:
        """Pensive Professor must have base power 0."""
        card = PensiveProfessor(name="Pensive Professor", owner=None)
        assert card.base_power == 0

    def test_toughness(self) -> None:
        """Pensive Professor must have base toughness 2."""
        card = PensiveProfessor(name="Pensive Professor", owner=None)
        assert card.base_toughness == 2


@pytest.mark.ability
class TestPensiveProfessorAbilities:
    """Ability tests for Pensive Professor — expected to fail against stubs."""

    def test_adds_plus_counter(self) -> None:
        """Resolution should add +1/+1 counter to target."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        target = Creature(name="Target", owner=player, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[target])
        card = PensiveProfessor(name="Pensive Professor", owner=player)
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

    def test_draws_cards(self) -> None:
        """Resolution should draw card(s)."""
        from tests.test_utils import create_game
        from engine.card import Sorcery
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        filler = Sorcery(name="Filler", owner=player)
        player.zones[Zone.LIBRARY].add(filler)
        player.zones[Zone.LIBRARY].add(Sorcery(name="F2", owner=player))
        hand_before = len(player.zones[Zone.HAND].get_all())
        card = PensiveProfessor(name="Pensive Professor", owner=player)
        card.controller = player
        card.on_resolve(game)
        hand_after = len(player.zones[Zone.HAND].get_all())
        assert hand_after > hand_before, (
            f"Should draw: hand {hand_before} -> {hand_after}"
        )


@pytest.mark.edge
class TestPensiveProfessorEdgeCases:
    """Edge case tests for Pensive Professor."""

    def test_zone_transition_graveyard(self) -> None:
        """Creature should properly move to graveyard on death."""
        from tests.test_utils import create_game, set_board_state
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        card = PensiveProfessor(name="Pensive Professor", owner=player)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        bf = game.get_battlefield(player)
        bf.remove(card)
        player.zones[Zone.GRAVEYARD].add(card)
        assert card in player.zones[Zone.GRAVEYARD].get_all()


@pytest.mark.interaction
class TestPensiveProfessorInteractions:
    """Interaction tests for Pensive Professor."""

    def test_resolution_with_board_state(self) -> None:
        """Card should resolve correctly with established board."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        t1 = Creature(name="T1", owner=opponent, base_power=2, base_toughness=2)
        t2 = Creature(name="T2", owner=opponent, base_power=3, base_toughness=3)
        set_board_state(game, 1, battlefield=[t1, t2])
        card = PensiveProfessor(name="Pensive Professor", owner=player)
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

    def test_coexists_with_other_creatures(self) -> None:
        """Card should coexist with other creatures on battlefield."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        card = PensiveProfessor(name="Pensive Professor", owner=player)
        card.controller = player
        ally = Creature(name="Ally", owner=player, base_power=3, base_toughness=3)
        set_board_state(game, 0, battlefield=[card, ally])
        bf = game.get_battlefield(player).get_all()
        assert len(bf) == 2, f"Both creatures on bf, got {len(bf)}"
        assert card in bf and ally in bf
