"""Audited tests for Joust Through (FDN collector number 19)."""

from __future__ import annotations

import pytest

from card_impl import JoustThrough

from engine.card import Creature, Instant, Sorcery, Artifact, Enchantment
from engine.types import CardType, ManaCost, ManaType, Zone
from tests.test_utils import create_game, set_board_state, cast_spell


def _make_creature(name="Bear", power=2, toughness=2, owner=None, controller=None):
    return Creature(name=name, base_power=power, base_toughness=toughness, owner=owner, controller=controller)



@pytest.mark.basic
class TestJoustThroughProperties:
    def test_is_instant(self):
        card = JoustThrough()
        assert isinstance(card, Instant)

    def test_name(self):
        card = JoustThrough()
        assert card.name == "Joust Through"

    def test_mana_cost(self):
        card = JoustThrough()
        assert card.mana_cost == ManaCost.parse("{W}")


@pytest.mark.ability
class TestJoustThroughResolution:
    def test_deals_3_damage(self):
        game = create_game()
        p1, p2 = game.players
        creature = _make_creature(owner=p2, controller=p2, toughness=5)
        set_board_state(game, 1, battlefield=[creature])
        spell = JoustThrough(owner=p1, controller=p1)
        spell.chosen_targets = [creature]
        spell.on_resolve(game)
        assert creature.damage_marked == 3

    def test_gains_1_life(self):
        game = create_game()
        p1 = game.players[0]
        creature = _make_creature(owner=p1, controller=p1, toughness=5)
        set_board_state(game, 0, battlefield=[creature])
        spell = JoustThrough(owner=p1, controller=p1)
        spell.chosen_targets = [creature]
        initial_life = p1.life
        spell.on_resolve(game)
        assert p1.life == initial_life + 1


@pytest.mark.edge
class TestJoustThroughEdge:
    def test_no_target_no_crash(self):
        game = create_game()
        spell = JoustThrough(owner=game.players[0], controller=game.players[0])
        spell.chosen_targets = []
        spell.on_resolve(game)
