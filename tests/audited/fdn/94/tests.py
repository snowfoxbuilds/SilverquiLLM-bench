"""Audited tests for Pox Plague (FDN collector number 94)."""

from __future__ import annotations

import pytest

from card_impl import PoxPlague

from engine.card import Creature, Instant, Sorcery, Artifact, Enchantment
from engine.types import CardType, ManaCost, ManaType, Zone
from tests.test_utils import create_game, set_board_state, cast_spell


def _make_creature(name="Bear", power=2, toughness=2, owner=None, controller=None):
    return Creature(name=name, base_power=power, base_toughness=toughness, owner=owner, controller=controller)



@pytest.mark.basic
class TestPoxPlagueProperties:
    def test_is_sorcery(self):
        card = PoxPlague()
        assert isinstance(card, Sorcery)

    def test_name(self):
        card = PoxPlague()
        assert card.name == "Pox Plague"


@pytest.mark.ability
class TestPoxPlagueResolution:
    def test_each_player_loses_life(self):
        game = create_game()
        p1, p2 = game.players
        spell = PoxPlague(owner=p1, controller=p1)
        spell.on_resolve(game)
        assert p1.life < 20
        assert p2.life < 20
