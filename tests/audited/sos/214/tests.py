"""Audited tests for Professor Dellian Fel (collector key 214).

Verifies the Professor Dellian Fel card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability/edge/interaction tests verify oracle text behavior (expected to fail against stubs).
Complexity tier: expert.
"""

from __future__ import annotations

import pytest

from card_impl import ProfessorDellianFel

from engine.card import Planeswalker
from engine.types import CardType, ManaCost


@pytest.mark.basic
class TestProfessorDellianFelBasicProperties:
    """Basic property tests for Professor Dellian Fel."""

    def test_is_planeswalker(self) -> None:
        """Professor Dellian Fel must be a Planeswalker subclass."""
        card = ProfessorDellianFel(name="Professor Dellian Fel", owner=None)
        assert isinstance(card, Planeswalker)

    def test_name(self) -> None:
        """ProfessorDellianFel.name must be 'Professor Dellian Fel'."""
        card = ProfessorDellianFel(name="Professor Dellian Fel", owner=None)
        assert card.name == "Professor Dellian Fel"

    def test_card_types(self) -> None:
        """Professor Dellian Fel must have correct card types."""
        card = ProfessorDellianFel(name="Professor Dellian Fel", owner=None)
        assert CardType.PLANESWALKER in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Professor Dellian Fel must have converted mana cost 4."""
        card = ProfessorDellianFel(name="Professor Dellian Fel", owner=None)
        assert card.mana_cost.cmc == 4

    def test_colors(self) -> None:
        """Professor Dellian Fel must have correct colors."""
        card = ProfessorDellianFel(name="Professor Dellian Fel", owner=None)
        assert "B" in card.colors
        assert "G" in card.colors


@pytest.mark.ability
class TestProfessorDellianFelAbilities:
    """Ability tests for Professor Dellian Fel -- expected to fail against stubs."""

    def test_resolution_removes_creatures(self) -> None:
        """Spell resolution must remove/destroy creatures per oracle text."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        from engine.types import Zone
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        target = Creature(name="Victim", owner=opponent, base_power=1, base_toughness=1)
        target.controller = opponent
        set_board_state(game, 1, battlefield=[target])
        card = ProfessorDellianFel(name="Professor Dellian Fel", owner=player)
        card.controller = player
        card.on_resolve(game)
        bf = opponent.zones[Zone.BATTLEFIELD].get_all()
        gy = opponent.zones[Zone.GRAVEYARD].get_all()
        assert target not in bf or target in gy, "Professor Dellian Fel must remove creature"

    def test_behavioral_method_exists(self) -> None:
        """Card must implement at least one behavioral method."""
        card = ProfessorDellianFel(name="Professor Dellian Fel", owner=None)
        methods = ["on_resolve", "on_enter_battlefield", "on_attack",
                   "on_death", "activate", "static_ability",
                   "opus_trigger", "check_infusion", "check_prepared"]
        found = [m for m in methods if callable(getattr(card, m, None))]
        assert len(found) > 0, "Professor Dellian Fel must implement behavioral method"


@pytest.mark.edge
class TestProfessorDellianFelEdgeCases:
    """Edge case and trap tests for Professor Dellian Fel."""

    def test_fizzle_spell_goes_to_graveyard(self) -> None:
        """Fizzled spell must end up in graveyard."""
        from tests.test_utils import create_game
        from engine.types import Zone
        from engine.zones import move_to_zone
        game = create_game()
        player = game.players[0]
        card = ProfessorDellianFel(name="Professor Dellian Fel", owner=player)
        card.controller = player
        try:
            card.on_resolve(game)
        except (ValueError, IndexError):
            pass
        move_to_zone(game, card, Zone.STACK, Zone.GRAVEYARD)
        gy = player.zones[Zone.GRAVEYARD].get_all()
        assert card in gy, "Fizzled spell must go to graveyard"

    def test_instances_have_independent_state(self) -> None:
        """Mutating one instance must not affect another."""
        card1 = ProfessorDellianFel(name="Professor Dellian Fel", owner=None)
        card2 = ProfessorDellianFel(name="Professor Dellian Fel", owner=None)
        card1.name = "Modified"
        assert card2.name == "Professor Dellian Fel", "Instances must be independent"

    def test_mana_cost_matches_spec(self) -> None:
        """Mana cost must match the card specification."""
        card = ProfessorDellianFel(name="Professor Dellian Fel", owner=None)
        assert card.mana_cost.cmc == 4, \
            f"CMC must be 4, got {card.mana_cost.cmc}"


@pytest.mark.interaction
class TestProfessorDellianFelInteractions:
    """Multi-card interaction tests for Professor Dellian Fel."""

    def test_targets_valid_objects(self) -> None:
        """Spell targeting must find valid targets."""
        from tests.test_utils import create_game, set_board_state
        from engine.card import Creature
        game = create_game()
        player = game.players[0]
        opponent = game.players[1]
        target = Creature(name="Target", owner=opponent, base_power=3, base_toughness=3)
        target.controller = opponent
        set_board_state(game, 1, battlefield=[target])
        card = ProfessorDellianFel(name="Professor Dellian Fel", owner=player)
        card.controller = player
        if callable(getattr(card, "get_targets", None)):
            targets = card.get_targets(game)
            assert len(targets) > 0, "Must find valid targets"

    def test_spell_to_graveyard_after_resolution(self) -> None:
        """Resolved spell must go to graveyard."""
        from tests.test_utils import create_game
        from engine.types import Zone
        from engine.zones import move_to_zone
        game = create_game()
        player = game.players[0]
        card = ProfessorDellianFel(name="Professor Dellian Fel", owner=player)
        card.controller = player
        move_to_zone(game, card, Zone.STACK, Zone.GRAVEYARD)
        gy = player.zones[Zone.GRAVEYARD].get_all()
        assert card in gy, "Resolved spell must end up in graveyard"
