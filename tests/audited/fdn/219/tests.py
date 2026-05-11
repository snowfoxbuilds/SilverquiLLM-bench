"""Audited tests for Rapturous Moment (FDN collector number 219)."""

from __future__ import annotations

import pytest

from card_impl import RapturousMoment

from engine.card import Creature, Instant, Sorcery, Artifact, Enchantment
from engine.types import CardType, ManaCost, ManaType, Zone
from tests.test_utils import create_game, set_board_state, cast_spell


def _make_creature(name="Bear", power=2, toughness=2, owner=None, controller=None):
    return Creature(name=name, base_power=power, base_toughness=toughness, owner=owner, controller=controller)


from engine.card import CardImpl


@pytest.mark.basic
class TestRapturousMomentProperties:
    def test_is_sorcery(self):
        card = RapturousMoment()
        assert isinstance(card, Sorcery)

    def test_name(self):
        card = RapturousMoment()
        assert card.name == "Rapturous Moment"


@pytest.mark.ability
class TestRapturousMomentResolution:
    def test_draws_three(self):
        game = create_game()
        p1 = game.players[0]
        for i in range(5):
            c = CardImpl(name=f"C{i}", owner=p1)
            p1.zones[Zone.LIBRARY].add(c)
        # Add cards to hand for discard
        for i in range(3):
            c = CardImpl(name=f"H{i}", owner=p1)
            p1.zones[Zone.HAND].add(c)
        spell = RapturousMoment(owner=p1, controller=p1)
        spell.on_resolve(game)
        # Net: drew 3, discarded 2 = +1 card
