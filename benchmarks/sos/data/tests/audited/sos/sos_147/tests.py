"""Audited tests for Environmental Scientist (collector number 147).

Verifies the Environmental Scientist card implementation against card_spec.json.
Basic tests verify stats/attributes (should pass against stubs).
Ability tests verify oracle text behavior (expected to fail against stubs).
"""
from __future__ import annotations

from test_utils import card_colors

import pytest
from card_impl import EnvironmentalScientist
from engine.card import Creature
from engine.types import CardType, ManaCost
from engine.events import EntersBattlefieldTriggeredEvent

@pytest.mark.basic
class TestEnvironmentalScientistBasicProperties:
    """Environmental Scientist basic property tests."""

    def test_is_creature(self) -> None:
        """Environmental Scientist must be a Creature subclass."""
        card = EnvironmentalScientist(name='Environmental Scientist', owner=None)
        assert isinstance(card, Creature)

    def test_name(self) -> None:
        """EnvironmentalScientist.name must be 'Environmental Scientist'."""
        card = EnvironmentalScientist(name='Environmental Scientist', owner=None)
        assert card.name == 'Environmental Scientist'

    def test_card_type(self) -> None:
        """Environmental Scientist must have CardType.CREATURE."""
        card = EnvironmentalScientist(name='Environmental Scientist', owner=None)
        assert CardType.CREATURE in card.card_types

    def test_mana_cost_cmc(self) -> None:
        """Environmental Scientist must have converted mana cost 2."""
        card = EnvironmentalScientist(name='Environmental Scientist', owner=None)
        assert card.mana_cost.cmc == 2

    def test_colors(self) -> None:
        """Environmental Scientist must have colors ['G']."""
        card = EnvironmentalScientist(name='Environmental Scientist', owner=None)
        for c in ['G']:
            assert c in card_colors(card), f'Expected color {c} in {card_colors(card)}'

    def test_power(self) -> None:
        """Environmental Scientist must have power 2."""
        card = EnvironmentalScientist(name='Environmental Scientist', owner=None)
        assert card.base_power == 2

    def test_toughness(self) -> None:
        """Environmental Scientist must have toughness 2."""
        card = EnvironmentalScientist(name='Environmental Scientist', owner=None)
        assert card.base_toughness == 2

@pytest.mark.ability
class TestEnvironmentalScientistAbilities:
    """Environmental Scientist ability tests — expected to fail against stubs."""

    def test_etb_searches_library(self) -> None:
        """Environmental Scientist ETB should search library.

        Oracle: When this creature enters, you may search your library for a basic land card, reveal it, put it into
        This test will fail against stubs (expected).
        """
        from test_utils import create_game, set_board_state
        from engine.types import Zone
        from engine.card import CardImpl, Land
        game = create_game()
        player = game.players[0]
        for i in range(5):
            lib_card = Land(name='Plains', owner=player)
            lib_card.subtypes = {'Plains'}
            player.zones[Zone.LIBRARY].add(lib_card)
        card = EnvironmentalScientist(name='Environmental Scientist', owner=player)
        card.controller = player
        set_board_state(game, 0, battlefield=[card])
        lib_before = len(player.zones[Zone.LIBRARY].get_all())
        card.register_triggers(game)
        game.trigger_manager.fire_event(game, EntersBattlefieldTriggeredEvent(card=card))
        lib_after = len(player.zones[Zone.LIBRARY].get_all())
        hand_after = len(player.zones[Zone.HAND].get_all())
        assert lib_after < lib_before or hand_after > 0, f'Expected library search on ETB. Lib: {lib_before}->{lib_after}, Hand: {hand_after}'
