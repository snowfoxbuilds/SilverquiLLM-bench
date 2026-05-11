"""Audited tests for Bite Down (FDN collector number 212)."""

from __future__ import annotations

import pytest

from card_impl import BiteDown

from engine.card import Creature, Instant, Sorcery, Artifact, Enchantment
from engine.types import CardType, ManaCost, ManaType, Zone
from tests.test_utils import create_game, set_board_state, cast_spell


def _make_creature(name="Bear", power=2, toughness=2, owner=None, controller=None):
    return Creature(name=name, base_power=power, base_toughness=toughness, owner=owner, controller=controller)



@pytest.mark.basic
class TestBiteDownProperties:
    def test_is_instant(self):
        card = BiteDown()
        assert isinstance(card, Instant)

    def test_name(self):
        card = BiteDown()
        assert card.name == "Bite Down"

    def test_mana_cost(self):
        card = BiteDown()
        assert card.mana_cost == ManaCost.parse("{1}{G}")


@pytest.mark.ability
class TestBiteDownResolution:
    def test_deals_damage_equal_to_power(self):
        game = create_game()
        p1, p2 = game.players
        my_creature = _make_creature(name="My Bear", power=4, toughness=4, owner=p1, controller=p1)
        their_creature = _make_creature(name="Their Bear", power=2, toughness=5, owner=p2, controller=p2)
        set_board_state(game, 0, battlefield=[my_creature])
        set_board_state(game, 1, battlefield=[their_creature])
        spell = BiteDown(owner=p1, controller=p1)
        spell.chosen_targets = [my_creature, their_creature]
        spell.on_resolve(game)
        assert their_creature.damage_marked == 4
