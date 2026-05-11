"""Audited tests for Bushwhack (FDN collector number 215)."""

from __future__ import annotations

import pytest

from card_impl import Bushwhack

from engine.card import Creature, Instant, Sorcery, Artifact, Enchantment
from engine.types import CardType, ManaCost, ManaType, Zone
from tests.test_utils import create_game, set_board_state, cast_spell


def _make_creature(name="Bear", power=2, toughness=2, owner=None, controller=None):
    return Creature(name=name, base_power=power, base_toughness=toughness, owner=owner, controller=controller)



@pytest.mark.basic
class TestBushwhackProperties:
    def test_is_sorcery(self):
        card = Bushwhack()
        assert isinstance(card, Sorcery)

    def test_name(self):
        card = Bushwhack()
        assert card.name == "Bushwhack"


@pytest.mark.ability
class TestBushwhackResolution:
    def test_mode_0_searches_for_basic_land(self):
        """Mode 0: Search library for a basic land card, put it into hand."""
        from engine.card import Land
        from engine.types import Supertype
        game = create_game()
        p1 = game.players[0]
        land = Land(name="Forest", owner=p1, controller=p1)
        land.supertypes = {Supertype.BASIC}
        p1.zones[Zone.LIBRARY].add(land)
        spell = Bushwhack(owner=p1, controller=p1)
        spell.chosen_mode = 0
        spell.on_resolve(game)
        hand = list(p1.zones[Zone.HAND].get_all())
        assert land in hand

    def test_mode_1_creatures_fight(self):
        """Mode 1: Two creatures fight each other."""
        game = create_game()
        p1, p2 = game.players
        my_creature = _make_creature(name="Wolf", power=3, toughness=3, owner=p1, controller=p1)
        opp_creature = _make_creature(name="Bear", power=2, toughness=2, owner=p2, controller=p2)
        set_board_state(game, 0, battlefield=[my_creature])
        set_board_state(game, 1, battlefield=[opp_creature])
        spell = Bushwhack(owner=p1, controller=p1)
        spell.chosen_mode = 1
        spell.chosen_targets = [my_creature, opp_creature]
        spell.on_resolve(game)
        assert opp_creature.damage_marked == 3
        assert my_creature.damage_marked == 2


@pytest.mark.edge
class TestBushwhackEdge:
    def test_no_mode_no_crash(self):
        game = create_game()
        spell = Bushwhack(owner=game.players[0], controller=game.players[0])
        spell.chosen_mode = None
        spell.on_resolve(game)
