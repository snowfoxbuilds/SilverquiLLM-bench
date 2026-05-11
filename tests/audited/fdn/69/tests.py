"""Audited tests for Seeker's Folly (FDN collector number 69)."""

from __future__ import annotations

import pytest

from card_impl import SeekersFolly

from engine.card import Creature, Instant, Sorcery, Artifact, Enchantment
from engine.types import CardType, ManaCost, ManaType, Zone
from tests.test_utils import create_game, set_board_state, cast_spell


def _make_creature(name="Bear", power=2, toughness=2, owner=None, controller=None):
    return Creature(name=name, base_power=power, base_toughness=toughness, owner=owner, controller=controller)



@pytest.mark.basic
class TestSeekersFollyProperties:
    def test_is_sorcery(self):
        card = SeekersFolly()
        assert isinstance(card, Sorcery)

    def test_name(self):
        card = SeekersFolly()
        assert card.name == "Seeker\'s Folly"


@pytest.mark.ability
class TestSeekersFollyResolution:
    def test_mode_0_opponent_discards_two(self):
        """Mode 0: Target opponent discards two cards."""
        game = create_game()
        p1, p2 = game.players
        c1 = Creature(name="Card1", base_power=1, base_toughness=1, owner=p2, controller=p2)
        c2 = Creature(name="Card2", base_power=1, base_toughness=1, owner=p2, controller=p2)
        p2.zones[Zone.HAND].add(c1)
        p2.zones[Zone.HAND].add(c2)
        spell = SeekersFolly(owner=p1, controller=p1)
        spell.chosen_mode = 0
        spell.chosen_targets = [p2]
        spell.on_resolve(game)
        hand = list(p2.zones[Zone.HAND].get_all())
        assert len(hand) == 0

    def test_mode_1_shrinks_opponent_creatures(self):
        """Mode 1: Creatures opponents control get -1/-1 until EOT."""
        game = create_game()
        p1, p2 = game.players
        creature = _make_creature(name="Bear", power=3, toughness=3, owner=p2, controller=p2)
        set_board_state(game, 1, battlefield=[creature])
        spell = SeekersFolly(owner=p1, controller=p1)
        spell.chosen_mode = 1
        spell.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert creature.power == 2
        assert creature.toughness == 2


@pytest.mark.edge
class TestSeekersFollyEdge:
    def test_no_mode_no_crash(self):
        game = create_game()
        spell = SeekersFolly(owner=game.players[0], controller=game.players[0])
        spell.chosen_mode = None
        spell.on_resolve(game)
