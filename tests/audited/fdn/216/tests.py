"""Audited tests for Pursue the Past (FDN collector number 216)."""

from __future__ import annotations

import pytest

from card_impl import PursueThePast

from engine.card import Creature, Instant, Sorcery, Artifact, Enchantment
from engine.types import CardType, ManaCost, ManaType, Zone
from tests.test_utils import create_game, set_board_state, cast_spell


def _make_creature(name="Bear", power=2, toughness=2, owner=None, controller=None):
    return Creature(name=name, base_power=power, base_toughness=toughness, owner=owner, controller=controller)



@pytest.mark.basic
class TestPursueThePastProperties:
    def test_is_sorcery(self):
        card = PursueThePast()
        assert isinstance(card, Sorcery)

    def test_name(self):
        card = PursueThePast()
        assert card.name == "Pursue the Past"


@pytest.mark.ability
class TestPursueThePastResolution:
    def test_gains_2_life(self):
        game = create_game()
        p1 = game.players[0]
        spell = PursueThePast(owner=p1, controller=p1)
        initial_life = p1.life
        spell.on_resolve(game)
        assert p1.life == initial_life + 2
