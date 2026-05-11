"""Audited tests for Primal Might (FDN collector number 643)."""

from __future__ import annotations

import pytest

from card_impl import PrimalMight

from engine.card import Creature, Instant, Sorcery, Artifact, Enchantment
from engine.types import CardType, ManaCost, ManaType, Zone
from tests.test_utils import create_game, set_board_state, cast_spell


def _make_creature(name="Bear", power=2, toughness=2, owner=None, controller=None):
    return Creature(name=name, base_power=power, base_toughness=toughness, owner=owner, controller=controller)



@pytest.mark.basic
class TestPrimalMightProperties:
    def test_is_sorcery(self):
        card = PrimalMight()
        assert isinstance(card, Sorcery)

    def test_name(self):
        card = PrimalMight()
        assert card.name == "Primal Might"


@pytest.mark.ability
class TestPrimalMightResolution:
    def test_pumps_creature_and_fights(self):
        game = create_game()
        p1, p2 = game.players
        my_creature = _make_creature(name="MC", power=2, toughness=4, owner=p1, controller=p1)
        their_creature = _make_creature(name="TC", power=1, toughness=5, owner=p2, controller=p2)
        set_board_state(game, 0, battlefield=[my_creature])
        set_board_state(game, 1, battlefield=[their_creature])
        spell = PrimalMight(owner=p1, controller=p1)
        spell.x_value = 3
        spell.chosen_targets = [my_creature, their_creature]
        spell.on_resolve(game)
        game.effect_manager.apply_all(game)
        # My creature got +3/+3, then fights
        assert their_creature.damage_marked >= 5  # 2 + 3 from pump

    def test_x_zero_no_pump(self):
        """With X=0, creature gets +0/+0 (no change) but still fights."""
        game = create_game()
        p1, p2 = game.players
        my_creature = _make_creature(name="MC", power=3, toughness=3, owner=p1, controller=p1)
        their_creature = _make_creature(name="TC", power=2, toughness=4, owner=p2, controller=p2)
        set_board_state(game, 0, battlefield=[my_creature])
        set_board_state(game, 1, battlefield=[their_creature])
        spell = PrimalMight(owner=p1, controller=p1)
        spell.x_value = 0
        spell.chosen_targets = [my_creature, their_creature]
        spell.on_resolve(game)
        assert their_creature.damage_marked == 3  # no pump, base power
        assert my_creature.damage_marked == 2


@pytest.mark.edge
class TestPrimalMightEdge:
    def test_no_targets_no_crash(self):
        game = create_game()
        p1 = game.players[0]
        spell = PrimalMight(owner=p1, controller=p1)
        spell.x_value = 3
        spell.chosen_targets = []
        spell.on_resolve(game)
