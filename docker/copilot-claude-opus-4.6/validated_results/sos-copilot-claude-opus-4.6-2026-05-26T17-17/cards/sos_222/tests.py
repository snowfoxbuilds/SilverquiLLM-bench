"""Tests for SOS 222 — Root Manipulation.

A sorcery costing {3}{B}{G}: Until end of turn, creatures you control get +2/+2
and gain menace and "Whenever this creature attacks, you gain 1 life."
"""

from __future__ import annotations

from cards.sos.sos_222.card_impl import RootManipulation
from engine.card import Creature, Sorcery
from engine.types import Keyword, ManaCost, ManaType, Zone
from test_utils import create_game, set_board_state, cast_spell


class TestRootManipulationProperties:
    """Static card data should match the SOS 222 spec."""

    def test_is_sorcery(self) -> None:
        assert isinstance(RootManipulation(owner=None), Sorcery)

    def test_name(self) -> None:
        assert RootManipulation(owner=None).name == "Root Manipulation"

    def test_mana_cost(self) -> None:
        assert RootManipulation(owner=None).mana_cost == ManaCost.parse("{3}{B}{G}")


class TestRootManipulationEffect:
    """Until end of turn, creatures you control get +2/+2, menace, and
    'Whenever this creature attacks, you gain 1 life.'"""

    def test_creatures_get_plus_two_plus_two(self) -> None:
        game = create_game()
        p1 = game.players[0]
        bear = Creature(name="Bear", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)
        game.get_battlefield(p1).add(bear)
        spell = RootManipulation(owner=p1, controller=p1)
        spell.on_resolve(game)
        assert bear.power == 4
        assert bear.toughness == 4

    def test_creatures_gain_menace(self) -> None:
        game = create_game()
        p1 = game.players[0]
        bear = Creature(name="Bear", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)
        game.get_battlefield(p1).add(bear)
        spell = RootManipulation(owner=p1, controller=p1)
        spell.on_resolve(game)
        assert Keyword.MENACE in bear.keywords

    def test_does_not_affect_opponent_creatures(self) -> None:
        game = create_game()
        p1 = game.players[0]
        p2 = game.players[1]
        enemy = Creature(name="Enemy", owner=p2, controller=p2,
                         base_power=3, base_toughness=3)
        game.get_battlefield(p2).add(enemy)
        spell = RootManipulation(owner=p1, controller=p1)
        spell.on_resolve(game)
        assert enemy.power == 3
        assert enemy.toughness == 3

    def test_attack_trigger_gains_life(self) -> None:
        """Each creature that attacks should trigger 'you gain 1 life'."""
        game = create_game()
        p1 = game.players[0]
        bear = Creature(name="Bear", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)
        game.get_battlefield(p1).add(bear)
        spell = RootManipulation(owner=p1, controller=p1)
        spell.on_resolve(game)

        life_before = game.players[0].life
        # Simulate the attack trigger
        bear.trigger_attack(game)
        assert game.players[0].life == life_before + 1

    def test_effect_is_temporary_until_end_of_turn(self) -> None:
        """The +2/+2 and menace should wear off at end of turn."""
        game = create_game()
        p1 = game.players[0]
        bear = Creature(name="Bear", owner=p1, controller=p1,
                        base_power=2, base_toughness=2)
        game.get_battlefield(p1).add(bear)
        spell = RootManipulation(owner=p1, controller=p1)
        spell.on_resolve(game)
        # End the turn
        game.end_turn()
        assert bear.power == 2
        assert bear.toughness == 2
        assert Keyword.MENACE not in bear.keywords

    def test_multiple_creatures_all_buffed(self) -> None:
        """All creatures you control get the buff, not just one."""
        game = create_game()
        p1 = game.players[0]
        bear1 = Creature(name="Bear1", owner=p1, controller=p1,
                         base_power=2, base_toughness=2)
        bear2 = Creature(name="Bear2", owner=p1, controller=p1,
                         base_power=1, base_toughness=1)
        game.get_battlefield(p1).add(bear1)
        game.get_battlefield(p1).add(bear2)
        spell = RootManipulation(owner=p1, controller=p1)
        spell.on_resolve(game)
        assert bear1.power == 4
        assert bear2.power == 3
