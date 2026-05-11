"""Audited tests for Giant Growth (FDN collector number 223)."""

from __future__ import annotations

import pytest

from card_impl import GiantGrowth

from engine.card import Creature, Instant, Sorcery, Artifact, Enchantment
from engine.types import CardType, ManaCost, ManaType, Zone
from tests.test_utils import create_game, set_board_state, cast_spell


def _make_creature(name="Bear", power=2, toughness=2, owner=None, controller=None):
    return Creature(name=name, base_power=power, base_toughness=toughness, owner=owner, controller=controller)



@pytest.mark.basic
class TestGiantGrowthProperties:
    def test_is_instant(self):
        card = GiantGrowth()
        assert isinstance(card, Instant)

    def test_name(self):
        card = GiantGrowth()
        assert card.name == "Giant Growth"

    def test_mana_cost(self):
        card = GiantGrowth()
        assert card.mana_cost == ManaCost.parse("{G}")


@pytest.mark.ability
class TestGiantGrowthResolution:
    def test_gives_plus_3_3(self):
        game = create_game()
        p1 = game.players[0]
        creature = _make_creature(owner=p1, controller=p1, power=2, toughness=2)
        set_board_state(game, 0, battlefield=[creature])
        spell = GiantGrowth(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[spell], mana={ManaType.GREEN: 1})
        cast_spell(game, 0, "Giant Growth", targets=[creature])
        game.effect_manager.apply_all(game)
        assert creature.power == 5
        assert creature.toughness == 5


@pytest.mark.edge
class TestGiantGrowthEdgeCases:
    def test_no_target_no_crash(self):
        game = create_game()
        p1 = game.players[0]
        spell = GiantGrowth(owner=p1, controller=p1)
        spell.chosen_targets = []
        spell.on_resolve(game)

    def test_target_left_battlefield_no_effect(self):
        game = create_game()
        p1 = game.players[0]
        creature = _make_creature(owner=p1, controller=p1)
        spell = GiantGrowth(owner=p1, controller=p1)
        spell.chosen_targets = [creature]
        # creature not on battlefield
        spell.on_resolve(game)
        # No continuous effect should be applied
        assert creature.power == 2
