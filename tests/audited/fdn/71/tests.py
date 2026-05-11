"""Audited tests for Wisdom of Ages (FDN collector number 71)."""

from __future__ import annotations

import pytest

from card_impl import WisdomOfAges

from engine.card import Creature, Instant, Sorcery, Artifact, Enchantment
from engine.types import CardType, ManaCost, ManaType, Zone
from tests.test_utils import create_game, set_board_state, cast_spell


def _make_creature(name="Bear", power=2, toughness=2, owner=None, controller=None):
    return Creature(name=name, base_power=power, base_toughness=toughness, owner=owner, controller=controller)


from engine.card import CardImpl


@pytest.mark.basic
class TestWisdomOfAgesProperties:
    def test_is_sorcery(self):
        card = WisdomOfAges()
        assert isinstance(card, Sorcery)

    def test_name(self):
        card = WisdomOfAges()
        assert card.name == "Wisdom of Ages"


@pytest.mark.ability
class TestWisdomOfAgesResolution:
    def test_returns_instants_sorceries_from_graveyard(self):
        game = create_game()
        p1 = game.players[0]
        instant = Instant(name="Test Instant", owner=p1, controller=p1)
        sorcery = Sorcery(name="Test Sorcery", owner=p1, controller=p1)
        creature = _make_creature(name="Bear", owner=p1, controller=p1)
        set_board_state(game, 0, graveyard=[instant, sorcery, creature])
        spell = WisdomOfAges(owner=p1, controller=p1)
        spell.on_resolve(game)
        hand = [c.name for c in p1.zones[Zone.HAND].get_all()]
        assert "Test Instant" in hand
        assert "Test Sorcery" in hand
        gy = [c.name for c in p1.zones[Zone.GRAVEYARD].get_all()]
        assert "Bear" in gy
