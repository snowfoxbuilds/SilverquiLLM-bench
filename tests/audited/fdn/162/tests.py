"""Audited tests for Run Away Together (FDN collector number 162)."""

from __future__ import annotations

import pytest

from card_impl import RunAwayTogether

from engine.card import Creature, Instant, Sorcery, Artifact, Enchantment
from engine.types import CardType, ManaCost, ManaType, Zone
from tests.test_utils import create_game, set_board_state, cast_spell


def _make_creature(name="Bear", power=2, toughness=2, owner=None, controller=None):
    return Creature(name=name, base_power=power, base_toughness=toughness, owner=owner, controller=controller)



@pytest.mark.ability
class TestRunAwayTogetherResolution:
    def test_bounces_two_creatures(self):
        """Returns two creatures controlled by different players to hand."""
        game = create_game()
        p1, p2 = game.players
        c1 = _make_creature(name="Cat", power=1, toughness=1, owner=p1, controller=p1)
        c2 = _make_creature(name="Bear", power=2, toughness=2, owner=p2, controller=p2)
        set_board_state(game, 0, battlefield=[c1])
        set_board_state(game, 1, battlefield=[c2])
        spell = RunAwayTogether(owner=p1, controller=p1)
        spell.chosen_targets = [c1, c2]
        spell.on_resolve(game)
        bf1 = list(game.get_battlefield(p1).get_all())
        bf2 = list(game.get_battlefield(p2).get_all())
        assert c1 not in bf1
        assert c2 not in bf2


@pytest.mark.edge
class TestRunAwayTogetherEdge:
    def test_one_target_gone_still_bounces_other(self):
        """If one target left battlefield, the other is still bounced."""
        game = create_game()
        p1, p2 = game.players
        c1 = _make_creature(name="Cat", power=1, toughness=1, owner=p1, controller=p1)
        c2 = _make_creature(name="Bear", power=2, toughness=2, owner=p2, controller=p2)
        # Only c2 on battlefield; c1 already gone
        set_board_state(game, 1, battlefield=[c2])
        spell = RunAwayTogether(owner=p1, controller=p1)
        spell.chosen_targets = [c1, c2]
        spell.on_resolve(game)
        bf2 = list(game.get_battlefield(p2).get_all())
        assert c2 not in bf2
    def test_is_instant(self):
        card = RunAwayTogether()
        assert isinstance(card, Instant)

    def test_name(self):
        card = RunAwayTogether()
        assert card.name == "Run Away Together"

    def test_mana_cost(self):
        card = RunAwayTogether()
        assert card.mana_cost == ManaCost.parse("{1}{U}")
