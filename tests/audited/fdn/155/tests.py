"""Audited tests for Fleeting Distraction (FDN collector number 155)."""

from __future__ import annotations

import pytest

from card_impl import FleetingDistraction

from engine.card import Creature, Instant, Sorcery, Artifact, Enchantment
from engine.types import CardType, ManaCost, ManaType, Zone
from tests.test_utils import create_game, set_board_state, cast_spell


def _make_creature(name="Bear", power=2, toughness=2, owner=None, controller=None):
    return Creature(name=name, base_power=power, base_toughness=toughness, owner=owner, controller=controller)


from engine.card import CardImpl


@pytest.mark.basic
class TestFleetingDistractionProperties:
    def test_is_instant(self):
        card = FleetingDistraction()
        assert isinstance(card, Instant)

    def test_name(self):
        card = FleetingDistraction()
        assert card.name == "Fleeting Distraction"


@pytest.mark.ability
class TestFleetingDistractionResolution:
    def test_draws_a_card(self):
        game = create_game()
        p1 = game.players[0]
        for i in range(3):
            c = CardImpl(name=f"C{i}", owner=p1)
            p1.zones[Zone.LIBRARY].add(c)
        creature = _make_creature(owner=p1, controller=p1, power=3, toughness=3)
        set_board_state(game, 0, battlefield=[creature])
        spell = FleetingDistraction(owner=p1, controller=p1)
        spell.chosen_targets = [creature]
        initial_hand = len(list(p1.zones[Zone.HAND].get_all()))
        spell.on_resolve(game)
        final_hand = len(list(p1.zones[Zone.HAND].get_all()))
        assert final_hand == initial_hand + 1
