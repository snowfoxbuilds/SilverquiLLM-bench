"""Audited tests for FDN 212 — Bite Down."""

from __future__ import annotations

from card_impl import BiteDown
from engine.card import Creature, Instant
from engine.types import CardType, ManaCost
from tests.test_utils import create_game


class TestBiteDownBasics:
    """Basic card properties."""

    def test_name(self) -> None:
        card = BiteDown(owner=None)
        assert card.name == "Bite Down"

    def test_mana_cost(self) -> None:
        card = BiteDown(owner=None)
        assert card.mana_cost == ManaCost.parse("{1}{G}")

    def test_is_instant(self) -> None:
        card = BiteDown(owner=None)
        assert isinstance(card, Instant)


class TestBiteDownResolve:
    """Spell resolution: your creature deals damage to opponent creature."""

    def test_deals_damage_equal_to_power(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        my_creature = Creature(name="Big Guy", base_power=5, base_toughness=5, owner=p1, controller=p1)
        game.get_battlefield(p1).add(my_creature)
        opp_creature = Creature(name="Bear", base_power=2, base_toughness=2, owner=p2, controller=p2)
        game.get_battlefield(p2).add(opp_creature)
        spell = BiteDown(owner=p1, controller=p1)
        spell.chosen_targets = [my_creature, opp_creature]
        spell.on_resolve(game)
        assert opp_creature.damage_marked == 5

    def test_no_damage_if_source_gone(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        my_creature = Creature(name="Big Guy", base_power=5, base_toughness=5, owner=p1, controller=p1)
        # Not on battlefield
        opp_creature = Creature(name="Bear", base_power=2, base_toughness=2, owner=p2, controller=p2)
        game.get_battlefield(p2).add(opp_creature)
        spell = BiteDown(owner=p1, controller=p1)
        spell.chosen_targets = [my_creature, opp_creature]
        spell.on_resolve(game)
        assert opp_creature.damage_marked == 0

    def test_no_damage_if_target_gone(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        my_creature = Creature(name="Big Guy", base_power=5, base_toughness=5, owner=p1, controller=p1)
        game.get_battlefield(p1).add(my_creature)
        opp_creature = Creature(name="Bear", base_power=2, base_toughness=2, owner=p2, controller=p2)
        # Not on battlefield
        spell = BiteDown(owner=p1, controller=p1)
        spell.chosen_targets = [my_creature, opp_creature]
        spell.on_resolve(game)
        # No damage since target left battlefield
        assert opp_creature.damage_marked == 0

