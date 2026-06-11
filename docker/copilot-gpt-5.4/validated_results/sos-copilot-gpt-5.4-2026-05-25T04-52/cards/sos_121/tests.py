"""Tests for SOS 121 — Living History."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_121.card_impl import LivingHistory
from benchmarks.sos.workspace.engine.card import Creature, Enchantment, CardImpl
from benchmarks.sos.workspace.engine.casting import resolve_top
from benchmarks.sos.workspace.engine.events import AttacksTriggeredEvent
from benchmarks.sos.workspace.engine.types import Color, ManaCost, Zone
from benchmarks.sos.workspace.engine.zones import move_to_zone
from benchmarks.sos.workspace.tests.test_utils import create_game, declare_attackers, set_board_state


class TestLivingHistoryProperties:
    """Static card data should match the SOS 121 spec."""

    def test_is_enchantment(self) -> None:
        assert isinstance(LivingHistory(owner=None), Enchantment)

    def test_name_and_mana_cost(self) -> None:
        card = LivingHistory(owner=None)
        assert card.name == "Living History"
        assert card.mana_cost == ManaCost.parse("{1}{R}")


class TestLivingHistoryEnters:
    """Living History should create a Spirit token when it resolves."""

    def test_on_resolve_creates_a_two_two_red_and_white_spirit_token(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LivingHistory(owner=p1, controller=p1)

        card.on_resolve(game)

        spirit_tokens = [
            obj
            for obj in game.get_battlefield(p1).get_all()
            if isinstance(obj, Creature) and "Spirit" in getattr(obj, "subtypes", set())
        ]
        assert len(spirit_tokens) == 1
        token = spirit_tokens[0]
        assert token.base_power == 2
        assert token.base_toughness == 2
        assert getattr(token, "colors", set()) == {Color.RED, Color.WHITE}
        assert token.is_token is True


class TestLivingHistoryAttackTrigger:
    """Living History should reward attacks after your graveyard was depleted."""

    def test_registers_an_attack_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = LivingHistory(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is AttacksTriggeredEvent

    def test_attacking_after_a_card_left_your_graveyard_puts_a_trigger_on_the_stack_and_gives_plus_two_power(self) -> None:
        game = create_game()
        p1 = game.players[0]
        enchantment = LivingHistory(owner=p1, controller=p1)
        attacker = Creature(
            name="Attacking Spirit",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        bystander = Creature(
            name="Studious Bystander",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        departed = CardImpl(name="Recovered Notes", owner=p1, controller=p1)
        attacker.summoning_sick = False
        bystander.summoning_sick = False
        set_board_state(game, 0, battlefield=[enchantment, attacker, bystander], graveyard=[departed])
        enchantment.register_triggers(game)
        move_to_zone(game, departed, Zone.GRAVEYARD, Zone.HAND)
        p1._script.append(attacker)

        declare_attackers(game, ["Attacking Spirit"])

        assert len(game.stack) == 1
        resolve_top(game)

        assert attacker.power == 4
        assert attacker.toughness == 2
        assert bystander.power == 2

        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)

        assert attacker.power == 2
        assert attacker.toughness == 2

    def test_attacking_without_a_card_leaving_your_graveyard_does_not_trigger_it(self) -> None:
        game = create_game()
        p1 = game.players[0]
        enchantment = LivingHistory(owner=p1, controller=p1)
        attacker = Creature(
            name="Attacking Spirit",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        attacker.summoning_sick = False
        set_board_state(game, 0, battlefield=[enchantment, attacker])
        enchantment.register_triggers(game)

        declare_attackers(game, ["Attacking Spirit"])

        assert game.stack.is_empty()
