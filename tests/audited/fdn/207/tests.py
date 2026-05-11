"""Audited tests for Slagstorm (FDN collector number 207)."""

from __future__ import annotations

import pytest

from card_impl import Slagstorm

from engine.card import Creature, Instant, Sorcery, Artifact, Enchantment
from engine.types import CardType, ManaCost, ManaType, Zone
from tests.test_utils import create_game, set_board_state, cast_spell


def _make_creature(name="Bear", power=2, toughness=2, owner=None, controller=None):
    return Creature(name=name, base_power=power, base_toughness=toughness, owner=owner, controller=controller)



@pytest.mark.basic
class TestSlagstormProperties:
    def test_is_sorcery(self):
        card = Slagstorm()
        assert isinstance(card, Sorcery)

    def test_name(self):
        card = Slagstorm()
        assert card.name == "Slagstorm"


@pytest.mark.ability
class TestSlagstormResolution:
    def test_mode_0_deals_3_to_each_creature(self):
        game = create_game()
        p1, p2 = game.players
        c1 = _make_creature(name="C1", power=2, toughness=5, owner=p1, controller=p1)
        c2 = _make_creature(name="C2", power=2, toughness=5, owner=p2, controller=p2)
        set_board_state(game, 0, battlefield=[c1])
        set_board_state(game, 1, battlefield=[c2])
        spell = Slagstorm(owner=p1, controller=p1)
        spell.chosen_mode = 0
        spell.on_resolve(game)
        assert c1.damage_marked == 3
        assert c2.damage_marked == 3

    def test_mode_1_deals_3_to_each_player(self):
        game = create_game()
        p1, p2 = game.players
        spell = Slagstorm(owner=p1, controller=p1)
        spell.chosen_mode = 1
        spell.on_resolve(game)
        assert p1.life == 17
        assert p2.life == 17


@pytest.mark.edge
class TestSlagstormEdge:
    def test_no_mode_no_crash(self):
        game = create_game()
        spell = Slagstorm(owner=game.players[0], controller=game.players[0])
        spell.chosen_mode = None
        spell.on_resolve(game)
