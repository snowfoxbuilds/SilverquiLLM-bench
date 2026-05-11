"""Audited tests for Goblin Surprise (FDN collector number 200)."""

from __future__ import annotations

import pytest

from card_impl import GoblinSurprise

from engine.card import Creature, Instant, Sorcery, Artifact, Enchantment
from engine.types import CardType, ManaCost, ManaType, Zone
from tests.test_utils import create_game, set_board_state, cast_spell


def _make_creature(name="Bear", power=2, toughness=2, owner=None, controller=None):
    return Creature(name=name, base_power=power, base_toughness=toughness, owner=owner, controller=controller)



@pytest.mark.basic
class TestGoblinSurpriseProperties:
    def test_is_instant(self):
        card = GoblinSurprise()
        assert isinstance(card, Instant)

    def test_name(self):
        card = GoblinSurprise()
        assert card.name == "Goblin Surprise"


@pytest.mark.ability
class TestGoblinSurpriseResolution:
    def test_mode_0_pumps_creatures(self):
        """Mode 0: Creatures you control get +2/+0 until end of turn."""
        game = create_game()
        p1 = game.players[0]
        creature = _make_creature(name="Goblin", power=1, toughness=1, owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[creature])
        spell = GoblinSurprise(owner=p1, controller=p1)
        spell.chosen_mode = 0
        spell.on_resolve(game)
        game.effect_manager.apply_all(game)
        assert creature.power == 3

    def test_mode_1_creates_two_goblin_tokens(self):
        """Mode 1: Create two 1/1 red Goblin creature tokens."""
        game = create_game()
        p1 = game.players[0]
        spell = GoblinSurprise(owner=p1, controller=p1)
        spell.chosen_mode = 1
        spell.on_resolve(game)
        bf = list(game.get_battlefield(p1).get_all())
        goblins = [c for c in bf if getattr(c, "name", "") == "Goblin"]
        assert len(goblins) == 2

    def test_mode_1_tokens_are_1_1(self):
        """Goblin tokens should be 1/1."""
        game = create_game()
        p1 = game.players[0]
        spell = GoblinSurprise(owner=p1, controller=p1)
        spell.chosen_mode = 1
        spell.on_resolve(game)
        bf = list(game.get_battlefield(p1).get_all())
        goblins = [c for c in bf if getattr(c, "name", "") == "Goblin"]
        for g in goblins:
            assert g.base_power == 1
            assert g.base_toughness == 1


@pytest.mark.edge
class TestGoblinSurpriseEdge:
    def test_no_mode_no_crash(self):
        game = create_game()
        spell = GoblinSurprise(owner=game.players[0], controller=game.players[0])
        spell.chosen_mode = None
        spell.on_resolve(game)
