"""Audited tests for Exsanguinate (FDN collector number 173)."""

from __future__ import annotations

import pytest

from card_impl import Exsanguinate

from engine.card import Creature, Instant, Sorcery, Artifact, Enchantment
from engine.types import CardType, ManaCost, ManaType, Zone
from tests.test_utils import create_game, set_board_state, cast_spell


def _make_creature(name="Bear", power=2, toughness=2, owner=None, controller=None):
    return Creature(name=name, base_power=power, base_toughness=toughness, owner=owner, controller=controller)



@pytest.mark.basic
class TestExsanguinateProperties:
    def test_is_sorcery(self):
        card = Exsanguinate()
        assert isinstance(card, Sorcery)

    def test_name(self):
        card = Exsanguinate()
        assert card.name == "Exsanguinate"


@pytest.mark.ability
class TestExsanguinateResolution:
    def test_drains_opponents(self):
        game = create_game()
        p1, p2 = game.players
        spell = Exsanguinate(owner=p1, controller=p1)
        spell.x_value = 3
        spell.on_resolve(game)
        assert p2.life == 17
        assert p1.life == 23


@pytest.mark.edge
class TestExsanguinateEdge:
    def test_x_zero(self):
        game = create_game()
        p1, p2 = game.players
        spell = Exsanguinate(owner=p1, controller=p1)
        spell.x_value = 0
        spell.on_resolve(game)
        assert p1.life == 20
        assert p2.life == 20
