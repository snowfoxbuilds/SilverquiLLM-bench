"""Tests for SOS 177 — Bogwater Lumaret."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_177.card_impl import BogwaterLumaret
from benchmarks.sos.workspace.engine.casting import resolve_top
from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.events import EntersBattlefieldTriggeredEvent
from benchmarks.sos.workspace.engine.types import ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestBogwaterLumaretProperties:
    """Static card data should match the SOS 177 spec."""

    def test_is_spirit_frog_creature(self) -> None:
        card = BogwaterLumaret(owner=None)

        assert isinstance(card, Creature)
        assert "Spirit" in card.subtypes
        assert "Frog" in card.subtypes

    def test_name_cost_and_power_toughness(self) -> None:
        card = BogwaterLumaret(owner=None)

        assert card.name == "Bogwater Lumaret"
        assert card.mana_cost == ManaCost.parse("{B}{G}")
        assert card.base_power == 2
        assert card.base_toughness == 2


class TestBogwaterLumaretEntersTrigger:
    """Bogwater Lumaret should gain life when your creatures enter."""

    def test_registers_an_enters_battlefield_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = BogwaterLumaret(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert any(trigger.event_type is EntersBattlefieldTriggeredEvent for trigger in triggers)

    def test_self_entry_puts_a_trigger_on_the_stack_and_gains_one_life(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = BogwaterLumaret(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=card, creature=card, controller=p1),
        )

        assert len(game.stack) == 1

        resolve_top(game)

        assert p1.life == 21

    def test_another_creature_you_control_entering_gains_one_life(self) -> None:
        game = create_game()
        p1 = game.players[0]
        lumaret = BogwaterLumaret(owner=p1, controller=p1)
        ally = Creature(
            name="Helpful Bear",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 0, battlefield=[lumaret, ally])
        lumaret.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=ally, creature=ally, controller=p1),
        )

        assert len(game.stack) == 1

        resolve_top(game)

        assert p1.life == 21

    def test_opponents_creature_entering_does_not_trigger_it(self) -> None:
        game = create_game()
        p1, p2 = game.players
        lumaret = BogwaterLumaret(owner=p1, controller=p1)
        enemy = Creature(
            name="Enemy Bear",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 0, battlefield=[lumaret])
        set_board_state(game, 1, battlefield=[enemy])
        lumaret.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=enemy, creature=enemy, controller=p2),
        )

        assert game.stack.is_empty()
        assert p1.life == 20

