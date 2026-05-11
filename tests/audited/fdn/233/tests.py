"""Audited tests for Snakeskin Veil (FDN collector number 233)."""

from __future__ import annotations

import pytest

from card_impl import SnakeskinVeil

from engine.card import Creature, Instant, Sorcery, Artifact, Enchantment
from engine.types import CardType, ManaCost, ManaType, Zone
from tests.test_utils import create_game, set_board_state, cast_spell


def _make_creature(name="Bear", power=2, toughness=2, owner=None, controller=None):
    return Creature(name=name, base_power=power, base_toughness=toughness, owner=owner, controller=controller)



@pytest.mark.basic
class TestSnakeskinVeilProperties:
    def test_is_instant(self):
        card = SnakeskinVeil()
        assert isinstance(card, Instant)

    def test_name(self):
        card = SnakeskinVeil()
        assert card.name == "Snakeskin Veil"

    def test_mana_cost(self):
        card = SnakeskinVeil()
        assert card.mana_cost == ManaCost.parse("{G}")


@pytest.mark.ability
class TestSnakeskinVeilResolution:
    def test_adds_counter(self):
        game = create_game()
        p1 = game.players[0]
        creature = _make_creature(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[creature])
        spell = SnakeskinVeil(owner=p1, controller=p1)
        spell.chosen_targets = [creature]
        spell.on_resolve(game)
        plus_counters = getattr(creature, "plus_one_counters", 0)
        assert plus_counters >= 1


@pytest.mark.edge
class TestSnakeskinVeilEdge:
    def test_no_target_no_crash(self):
        game = create_game()
        spell = SnakeskinVeil(owner=game.players[0], controller=game.players[0])
        spell.chosen_targets = []
        spell.on_resolve(game)
