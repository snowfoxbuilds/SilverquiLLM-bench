"""Audited tests for Embrace the Paradox (FDN collector number 186)."""

from __future__ import annotations

import pytest

from card_impl import EmbraceTheParadox

from engine.card import Creature, Instant, Sorcery, Artifact, Enchantment
from engine.types import CardType, ManaCost, ManaType, Zone
from tests.test_utils import create_game, set_board_state, cast_spell


def _make_creature(name="Bear", power=2, toughness=2, owner=None, controller=None):
    return Creature(name=name, base_power=power, base_toughness=toughness, owner=owner, controller=controller)


from engine.card import CardImpl


@pytest.mark.basic
class TestEmbraceTheParadoxProperties:
    def test_is_instant(self):
        card = EmbraceTheParadox()
        assert isinstance(card, Instant)

    def test_name(self):
        card = EmbraceTheParadox()
        assert card.name == "Embrace the Paradox"


@pytest.mark.ability
class TestEmbraceTheParadoxResolution:
    def test_draws_three(self):
        game = create_game()
        p1 = game.players[0]
        for i in range(5):
            c = CardImpl(name=f"C{i}", owner=p1)
            p1.zones[Zone.LIBRARY].add(c)
        spell = EmbraceTheParadox(owner=p1, controller=p1)
        spell.chosen_targets = []
        initial = len(list(p1.zones[Zone.HAND].get_all()))
        spell.on_resolve(game)
        final = len(list(p1.zones[Zone.HAND].get_all()))
        assert final == initial + 3

    def test_no_targets(self):
        game = create_game()
        card = EmbraceTheParadox()
        assert card.get_targets(game) == []
