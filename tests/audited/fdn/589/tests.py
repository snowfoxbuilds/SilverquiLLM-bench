"""Audited tests for Finale of Revelation (FDN collector number 589)."""

from __future__ import annotations

import pytest

from card_impl import FinaleOfRevelation

from engine.card import Creature, Instant, Sorcery, Artifact, Enchantment
from engine.types import CardType, ManaCost, ManaType, Zone
from tests.test_utils import create_game, set_board_state, cast_spell


def _make_creature(name="Bear", power=2, toughness=2, owner=None, controller=None):
    return Creature(name=name, base_power=power, base_toughness=toughness, owner=owner, controller=controller)


from engine.card import CardImpl


@pytest.mark.basic
class TestFinaleOfRevelationProperties:
    def test_is_sorcery(self):
        card = FinaleOfRevelation()
        assert isinstance(card, Sorcery)

    def test_name(self):
        card = FinaleOfRevelation()
        assert card.name == "Finale of Revelation"


@pytest.mark.ability
class TestFinaleOfRevelationResolution:
    def test_draws_x_cards(self):
        game = create_game()
        p1 = game.players[0]
        for i in range(10):
            c = CardImpl(name=f"C{i}", owner=p1)
            p1.zones[Zone.LIBRARY].add(c)
        spell = FinaleOfRevelation(owner=p1, controller=p1)
        spell.x_value = 3
        initial_hand = len(list(p1.zones[Zone.HAND].get_all()))
        spell.on_resolve(game)
        final_hand = len(list(p1.zones[Zone.HAND].get_all()))
        assert final_hand == initial_hand + 3

    def test_x_zero_draws_nothing(self):
        """With X=0, no cards should be drawn."""
        game = create_game()
        p1 = game.players[0]
        for i in range(5):
            c = CardImpl(name=f"C{i}", owner=p1)
            p1.zones[Zone.LIBRARY].add(c)
        spell = FinaleOfRevelation(owner=p1, controller=p1)
        spell.x_value = 0
        initial_hand = len(list(p1.zones[Zone.HAND].get_all()))
        spell.on_resolve(game)
        final_hand = len(list(p1.zones[Zone.HAND].get_all()))
        assert final_hand == initial_hand

    def test_x_10_shuffles_graveyard_into_library(self):
        """With X>=10, graveyard cards should be shuffled into library before drawing."""
        game = create_game()
        p1 = game.players[0]
        # Put cards in graveyard
        gy_cards = []
        for i in range(3):
            c = CardImpl(name=f"GY{i}", owner=p1)
            p1.zones[Zone.GRAVEYARD].add(c)
            gy_cards.append(c)
        # Put enough cards in library for the draw
        for i in range(15):
            c = CardImpl(name=f"Lib{i}", owner=p1)
            p1.zones[Zone.LIBRARY].add(c)
        spell = FinaleOfRevelation(owner=p1, controller=p1)
        spell.x_value = 10
        spell.on_resolve(game)
        # Graveyard should now be empty (all shuffled into library)
        gy_after = list(p1.zones[Zone.GRAVEYARD].get_all())
        assert len(gy_after) == 0, "Graveyard should be empty after shuffle into library"

    def test_x_10_draws_10_cards(self):
        """With X=10, should still draw 10 cards."""
        game = create_game()
        p1 = game.players[0]
        for i in range(20):
            c = CardImpl(name=f"Lib{i}", owner=p1)
            p1.zones[Zone.LIBRARY].add(c)
        spell = FinaleOfRevelation(owner=p1, controller=p1)
        spell.x_value = 10
        initial_hand = len(list(p1.zones[Zone.HAND].get_all()))
        spell.on_resolve(game)
        final_hand = len(list(p1.zones[Zone.HAND].get_all()))
        assert final_hand == initial_hand + 10

    def test_x_12_also_triggers_shuffle(self):
        """With X=12 (>10), graveyard should also be shuffled into library."""
        game = create_game()
        p1 = game.players[0]
        for i in range(3):
            c = CardImpl(name=f"GY{i}", owner=p1)
            p1.zones[Zone.GRAVEYARD].add(c)
        for i in range(20):
            c = CardImpl(name=f"Lib{i}", owner=p1)
            p1.zones[Zone.LIBRARY].add(c)
        spell = FinaleOfRevelation(owner=p1, controller=p1)
        spell.x_value = 12
        spell.on_resolve(game)
        gy_after = list(p1.zones[Zone.GRAVEYARD].get_all())
        assert len(gy_after) == 0

    def test_x_9_does_not_shuffle_graveyard(self):
        """With X=9 (<10), graveyard should NOT be shuffled."""
        game = create_game()
        p1 = game.players[0]
        for i in range(3):
            c = CardImpl(name=f"GY{i}", owner=p1)
            p1.zones[Zone.GRAVEYARD].add(c)
        for i in range(15):
            c = CardImpl(name=f"Lib{i}", owner=p1)
            p1.zones[Zone.LIBRARY].add(c)
        spell = FinaleOfRevelation(owner=p1, controller=p1)
        spell.x_value = 9
        spell.on_resolve(game)
        gy_after = list(p1.zones[Zone.GRAVEYARD].get_all())
        assert len(gy_after) == 3, "Graveyard should be unchanged with X<10"
