"""Tests for SOS 139 — Additive Evolution."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_139.card_impl import AdditiveEvolution
from benchmarks.sos.workspace.engine.casting import resolve_top
from benchmarks.sos.workspace.engine.card import Creature, Enchantment
from benchmarks.sos.workspace.engine.events import BeginningOfCombatTriggeredEvent, EntersBattlefieldTriggeredEvent
from benchmarks.sos.workspace.engine.protection import get_colors
from benchmarks.sos.workspace.engine.types import Color, Keyword, ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestAdditiveEvolutionProperties:
    """Static card data should match the SOS 139 spec."""

    def test_is_enchantment(self) -> None:
        assert isinstance(AdditiveEvolution(owner=None), Enchantment)

    def test_name_and_mana_cost(self) -> None:
        card = AdditiveEvolution(owner=None)
        assert card.name == "Additive Evolution"
        assert card.mana_cost == ManaCost.parse("{3}{G}{G}")


class TestAdditiveEvolutionTriggers:
    """Additive Evolution should make a Fractal and buff a creature at combat."""

    def test_registers_enter_and_beginning_of_combat_triggers(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = AdditiveEvolution(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 2
        assert {trigger.event_type for trigger in triggers} == {
            EntersBattlefieldTriggeredEvent,
            BeginningOfCombatTriggeredEvent,
        }

    def test_enters_trigger_creates_a_green_and_blue_fractal_token_with_three_plus_one_plus_one_counters(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = AdditiveEvolution(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=card, controller=p1),
        )

        assert len(game.stack) == 1
        resolve_top(game)

        tokens = [
            permanent
            for permanent in game.get_battlefield(p1).get_all()
            if getattr(permanent, "is_token", False)
        ]
        assert len(tokens) == 1
        token = tokens[0]
        assert isinstance(token, Creature)
        assert "Fractal" in token.subtypes
        assert get_colors(token) == {Color.GREEN, Color.BLUE}
        assert token.plus_one_counters == 3
        assert token.power == 3
        assert token.toughness == 3

    def test_beginning_of_combat_on_your_turn_puts_a_counter_on_target_creature_you_control_and_grants_vigilance_until_end_of_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = AdditiveEvolution(owner=p1, controller=p1)
        target = Creature(
            name="Fractal Student",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 0, battlefield=[card, target])
        p1.choose_target = lambda options, requirement: target
        card.register_triggers(game)

        game.trigger_manager.fire_event(game, BeginningOfCombatTriggeredEvent())

        assert len(game.stack) == 1
        resolve_top(game)

        assert target.plus_one_counters == 1
        assert Keyword.VIGILANCE in target.keywords

        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)

        assert target.plus_one_counters == 1
        assert Keyword.VIGILANCE not in target.keywords

    def test_beginning_of_combat_does_not_trigger_on_an_opponents_turn(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = AdditiveEvolution(owner=p1, controller=p1)
        target = Creature(
            name="Fractal Student",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 0, battlefield=[card, target])
        game.active_player_index = 1
        card.register_triggers(game)

        game.trigger_manager.fire_event(game, BeginningOfCombatTriggeredEvent())

        assert game.stack.is_empty()
        assert target.plus_one_counters == 0
        assert Keyword.VIGILANCE not in target.keywords
