"""Tests for SOS 101 — Sneering Shadewriter."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_101.card_impl import SneeringShadewriter
from benchmarks.sos.workspace.engine.casting import resolve_top
from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.events import EntersBattlefieldTriggeredEvent
from benchmarks.sos.workspace.engine.types import Keyword, ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestSneeringShadewriterProperties:
    """Static card data should match the SOS 101 spec."""

    def test_is_vampire_warlock_creature_with_flying(self) -> None:
        card = SneeringShadewriter(owner=None)

        assert isinstance(card, Creature)
        assert "Vampire" in card.subtypes
        assert "Warlock" in card.subtypes
        assert Keyword.FLYING in card.keywords

    def test_name_cost_and_power_toughness(self) -> None:
        card = SneeringShadewriter(owner=None)

        assert card.name == "Sneering Shadewriter"
        assert card.mana_cost == ManaCost.parse("{4}{B}")
        assert card.base_power == 3
        assert card.base_toughness == 3


class TestSneeringShadewriterTrigger:
    """Sneering Shadewriter should drain opponents when it enters."""

    def test_registers_an_enters_battlefield_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SneeringShadewriter(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is EntersBattlefieldTriggeredEvent

    def test_enters_trigger_puts_an_ability_on_the_stack_and_makes_each_opponent_lose_two_while_you_gain_two(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = SneeringShadewriter(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=card, creature=card, controller=p1),
        )

        assert len(game.stack) == 1
        resolve_top(game)

        assert p1.life == 22
        assert p2.life == 18
        assert getattr(p1, "life_gained_this_turn", 0) == 2
