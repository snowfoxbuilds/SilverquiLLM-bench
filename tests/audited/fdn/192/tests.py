"""Audited tests for Burst Lightning (FDN collector number 192)."""

from __future__ import annotations

import pytest

from card_impl import BurstLightning

from engine.card import Creature, Instant, Sorcery, Artifact, Enchantment
from engine.types import CardType, ManaCost, ManaType, Zone
from tests.test_utils import create_game, set_board_state, cast_spell


def _make_creature(name="Bear", power=2, toughness=2, owner=None, controller=None):
    return Creature(name=name, base_power=power, base_toughness=toughness, owner=owner, controller=controller)



@pytest.mark.basic
class TestBurstLightningProperties:
    def test_is_instant(self):
        card = BurstLightning()
        assert isinstance(card, Instant)

    def test_name(self):
        card = BurstLightning()
        assert card.name == "Burst Lightning"

    def test_mana_cost(self):
        card = BurstLightning()
        assert card.mana_cost == ManaCost.parse("{R}")


@pytest.mark.ability
class TestBurstLightningResolution:
    def test_deals_2_damage_to_creature(self):
        game = create_game()
        p1, p2 = game.players
        creature = _make_creature(owner=p2, controller=p2, toughness=5)
        set_board_state(game, 1, battlefield=[creature])
        bolt = BurstLightning(owner=p1, controller=p1)
        bolt.chosen_targets = [creature]
        bolt.on_resolve(game)
        assert creature.damage_marked == 2

    def test_deals_2_damage_to_player(self):
        game = create_game()
        p1, p2 = game.players
        bolt = BurstLightning(owner=p1, controller=p1)
        bolt.chosen_targets = [p2]
        bolt.on_resolve(game)
        assert p2.life == 18

    def test_kicked_deals_4_damage(self):
        game = create_game()
        p1, p2 = game.players
        creature = _make_creature(owner=p2, controller=p2, toughness=5)
        set_board_state(game, 1, battlefield=[creature])
        bolt = BurstLightning(owner=p1, controller=p1)
        bolt.kicked = True
        bolt.chosen_targets = [creature]
        bolt.on_resolve(game)
        assert creature.damage_marked == 4


@pytest.mark.edge
class TestBurstLightningEdgeCases:
    def test_no_target_fizzles(self):
        """If target is None, on_resolve does nothing."""
        game = create_game()
        p1 = game.players[0]
        bolt = BurstLightning(owner=p1, controller=p1)
        bolt.chosen_targets = []
        bolt.on_resolve(game)
        # No crash, no damage
        assert game.players[1].life == 20
