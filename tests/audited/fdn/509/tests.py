"""Audited tests for Into the Roil (FDN collector number 509)."""

from __future__ import annotations

import pytest

from card_impl import IntoTheRoil

from engine.card import Creature, Instant, Sorcery, Artifact, Enchantment
from engine.types import CardType, ManaCost, ManaType, Zone
from tests.test_utils import create_game, set_board_state, cast_spell


def _make_creature(name="Bear", power=2, toughness=2, owner=None, controller=None):
    return Creature(name=name, base_power=power, base_toughness=toughness, owner=owner, controller=controller)



@pytest.mark.basic
class TestIntoTheRoilProperties:
    def test_is_instant(self):
        card = IntoTheRoil()
        assert isinstance(card, Instant)

    def test_name(self):
        card = IntoTheRoil()
        assert card.name == "Into the Roil"


@pytest.mark.ability
class TestIntoTheRoilResolution:
    def test_bounces_nonland_permanent(self):
        game = create_game()
        p1, p2 = game.players
        creature = _make_creature(owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[creature])
        spell = IntoTheRoil(owner=p1, controller=p1)
        spell.chosen_targets = [creature]
        spell.kicked = False
        spell.on_resolve(game)
        bf = list(game.get_battlefield(p2).get_all())
        assert creature not in bf
        hand = list(p2.zones[Zone.HAND].get_all())
        assert creature in hand

    def test_kicked_bounces_and_draws(self):
        """When kicked, return target to hand AND draw a card."""
        game = create_game()
        p1, p2 = game.players
        creature = _make_creature(owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[creature])
        # Give p1 a card in library to draw
        draw_card = Creature(name="DrawTarget", base_power=1, base_toughness=1, owner=p1, controller=p1)
        p1.zones[Zone.LIBRARY].add(draw_card)
        initial_hand_size = len(list(p1.zones[Zone.HAND].get_all()))
        spell = IntoTheRoil(owner=p1, controller=p1)
        spell.chosen_targets = [creature]
        spell.kicked = True
        spell.on_resolve(game)
        bf = list(game.get_battlefield(p2).get_all())
        assert creature not in bf
        new_hand_size = len(list(p1.zones[Zone.HAND].get_all()))
        assert new_hand_size == initial_hand_size + 1

    def test_unkicked_does_not_draw(self):
        """When not kicked, only bounce—no card draw."""
        game = create_game()
        p1, p2 = game.players
        creature = _make_creature(owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[creature])
        draw_card = Creature(name="DrawTarget", base_power=1, base_toughness=1, owner=p1, controller=p1)
        p1.zones[Zone.LIBRARY].add(draw_card)
        initial_hand_size = len(list(p1.zones[Zone.HAND].get_all()))
        spell = IntoTheRoil(owner=p1, controller=p1)
        spell.chosen_targets = [creature]
        spell.kicked = False
        spell.on_resolve(game)
        new_hand_size = len(list(p1.zones[Zone.HAND].get_all()))
        assert new_hand_size == initial_hand_size


@pytest.mark.edge
class TestIntoTheRoilEdge:
    def test_no_target_no_crash(self):
        game = create_game()
        spell = IntoTheRoil(owner=game.players[0], controller=game.players[0])
        spell.chosen_targets = []
        spell.kicked = False
        spell.on_resolve(game)
