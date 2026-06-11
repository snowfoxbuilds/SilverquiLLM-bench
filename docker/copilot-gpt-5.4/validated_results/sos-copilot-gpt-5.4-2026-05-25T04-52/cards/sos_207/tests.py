"""Tests for SOS 207 — Old-Growth Educator."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_207.card_impl import OldGrowthEducator
from benchmarks.sos.workspace.engine.casting import resolve_top
from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.events import EntersBattlefieldTriggeredEvent
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestOldGrowthEducatorProperties:
    """Static card data should match the SOS 207 spec."""

    def test_is_treefolk_druid_creature_with_vigilance_and_reach(self) -> None:
        card = OldGrowthEducator(owner=None)

        assert isinstance(card, Creature)
        assert "Treefolk" in card.subtypes
        assert "Druid" in card.subtypes
        assert Keyword.VIGILANCE in card.keywords
        assert Keyword.REACH in card.keywords

    def test_name_cost_and_power_toughness(self) -> None:
        card = OldGrowthEducator(owner=None)

        assert card.name == "Old-Growth Educator"
        assert card.mana_cost == ManaCost.parse("{2}{B}{G}")
        assert card.base_power == 4
        assert card.base_toughness == 4


class TestOldGrowthEducatorInfusion:
    """Old-Growth Educator should only grow itself after a lifegain turn."""

    def test_registers_an_enters_battlefield_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = OldGrowthEducator(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is EntersBattlefieldTriggeredEvent

    def test_if_you_gained_life_this_turn_self_entry_puts_a_trigger_on_the_stack_and_adds_two_counters(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = OldGrowthEducator(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        p1.life_gained_this_turn = 1
        card.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=card, creature=card, controller=p1),
        )

        assert len(game.stack) == 1

        resolve_top(game)

        assert card.plus_one_counters == 2
        assert card.power == 6
        assert card.toughness == 6

    def test_without_life_gain_this_turn_self_entry_does_not_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = OldGrowthEducator(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=card, creature=card, controller=p1),
        )

        assert game.stack.is_empty()
        assert card.plus_one_counters == 0
        assert card.power == 4
        assert card.toughness == 4
