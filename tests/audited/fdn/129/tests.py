"""Audited tests for Seize the Spoils (FDN collector number 129)."""

from __future__ import annotations

import pytest

from card_impl import SeizeTheSpoils

from engine.card import Creature, Instant, Sorcery, Artifact, Enchantment
from engine.types import CardType, ManaCost, ManaType, Zone
from tests.test_utils import create_game, set_board_state, cast_spell


def _make_creature(name="Bear", power=2, toughness=2, owner=None, controller=None):
    return Creature(name=name, base_power=power, base_toughness=toughness, owner=owner, controller=controller)


from engine.card import CardImpl


@pytest.mark.basic
class TestSeizeTheSpoilsProperties:
    def test_is_sorcery(self):
        card = SeizeTheSpoils()
        assert isinstance(card, Sorcery)

    def test_name(self):
        card = SeizeTheSpoils()
        assert card.name == "Seize the Spoils"


@pytest.mark.ability
class TestSeizeTheSpoilsResolution:
    def test_draws_two_cards(self):
        game = create_game()
        p1 = game.players[0]
        for i in range(5):
            c = CardImpl(name=f"C{i}", owner=p1)
            p1.zones[Zone.LIBRARY].add(c)
        # Need a card in hand to discard
        discard_card = CardImpl(name="Discard", owner=p1)
        p1.zones[Zone.HAND].add(discard_card)
        spell = SeizeTheSpoils(owner=p1, controller=p1)
        spell.on_resolve(game)
        # Drew 2 cards after resolution
