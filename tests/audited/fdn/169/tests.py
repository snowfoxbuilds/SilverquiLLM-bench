"""Audited tests for Bake into a Pie (FDN collector number 169)."""

from __future__ import annotations

import pytest

from card_impl import BakeIntoAPie

from engine.card import Creature, Instant, Sorcery, Artifact, Enchantment
from engine.types import CardType, ManaCost, ManaType, Zone
from tests.test_utils import create_game, set_board_state, cast_spell


def _make_creature(name="Bear", power=2, toughness=2, owner=None, controller=None):
    return Creature(name=name, base_power=power, base_toughness=toughness, owner=owner, controller=controller)



@pytest.mark.basic
class TestBakeIntoAPieProperties:
    def test_is_instant(self):
        card = BakeIntoAPie()
        assert isinstance(card, Instant)

    def test_name(self):
        card = BakeIntoAPie()
        assert card.name == "Bake into a Pie"


@pytest.mark.ability
class TestBakeIntoAPieResolution:
    def test_destroys_creature(self):
        game = create_game()
        p1, p2 = game.players
        creature = _make_creature(owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[creature])
        spell = BakeIntoAPie(owner=p1, controller=p1)
        spell.chosen_targets = [creature]
        spell.on_resolve(game)
        bf = list(game.get_battlefield(p2).get_all())
        assert creature not in bf


@pytest.mark.edge
class TestBakeIntoAPieEdge:
    def test_target_left_battlefield(self):
        game = create_game()
        p1 = game.players[0]
        creature = _make_creature(owner=p1, controller=p1)
        spell = BakeIntoAPie(owner=p1, controller=p1)
        spell.chosen_targets = [creature]
        spell.on_resolve(game)
