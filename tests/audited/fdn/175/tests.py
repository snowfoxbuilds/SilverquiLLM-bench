"""Audited tests for Hero's Downfall (FDN collector number 175)."""

from __future__ import annotations

import pytest

from card_impl import HerosDownfall

from engine.card import Creature, Instant, Sorcery, Artifact, Enchantment
from engine.types import CardType, ManaCost, ManaType, Zone
from tests.test_utils import create_game, set_board_state, cast_spell


def _make_creature(name="Bear", power=2, toughness=2, owner=None, controller=None):
    return Creature(name=name, base_power=power, base_toughness=toughness, owner=owner, controller=controller)



@pytest.mark.basic
class TestHerosDownfallProperties:
    def test_is_instant(self):
        card = HerosDownfall()
        assert isinstance(card, Instant)

    def test_name(self):
        card = HerosDownfall()
        assert card.name == "Hero\'s Downfall"

    def test_mana_cost(self):
        card = HerosDownfall()
        assert card.mana_cost == ManaCost.parse("{1}{B}{B}")


@pytest.mark.ability
class TestHerosDownfallResolution:
    def test_destroys_creature(self):
        game = create_game()
        p1, p2 = game.players
        creature = _make_creature(owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[creature])
        spell = HerosDownfall(owner=p1, controller=p1)
        set_board_state(game, 0, hand=[spell], mana={ManaType.BLACK: 2, ManaType.COLORLESS: 1})
        cast_spell(game, 0, "Hero\'s Downfall", targets=[creature])
        bf = list(game.get_battlefield(p2).get_all())
        assert creature not in bf


@pytest.mark.edge
class TestHerosDownfallEdge:
    def test_no_target_no_crash(self):
        game = create_game()
        p1 = game.players[0]
        spell = HerosDownfall(owner=p1, controller=p1)
        spell.chosen_targets = []
        spell.on_resolve(game)

    def test_target_left_battlefield(self):
        game = create_game()
        p1 = game.players[0]
        creature = _make_creature(owner=p1, controller=p1)
        spell = HerosDownfall(owner=p1, controller=p1)
        spell.chosen_targets = [creature]
        spell.on_resolve(game)
        # Should not crash
