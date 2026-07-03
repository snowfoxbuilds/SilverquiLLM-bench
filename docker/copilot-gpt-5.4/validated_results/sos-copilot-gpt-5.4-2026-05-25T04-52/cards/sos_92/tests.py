"""Tests for SOS 92 — Poisoner's Apprentice."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_92.card_impl import PoisonersApprentice
from benchmarks.sos.workspace.engine.casting import resolve_top
from benchmarks.sos.workspace.engine.card import Creature
from benchmarks.sos.workspace.engine.events import EntersBattlefieldTriggeredEvent
from benchmarks.sos.workspace.engine.types import ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestPoisonersApprenticeProperties:
    """Static card data should match the SOS 92 spec."""

    def test_is_orc_warlock_creature(self) -> None:
        card = PoisonersApprentice(owner=None)

        assert isinstance(card, Creature)
        assert "Orc" in card.subtypes
        assert "Warlock" in card.subtypes

    def test_name_cost_and_power_toughness(self) -> None:
        card = PoisonersApprentice(owner=None)

        assert card.name == "Poisoner's Apprentice"
        assert card.mana_cost == ManaCost.parse("{2}{B}")
        assert card.base_power == 2
        assert card.base_toughness == 2


class TestPoisonersApprenticeInfusion:
    """Poisoner's Apprentice should shrink an opposing creature after infused entry."""

    def test_registers_an_enters_battlefield_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = PoisonersApprentice(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is EntersBattlefieldTriggeredEvent

    def test_if_you_gained_life_this_turn_self_entry_puts_a_trigger_on_the_stack_and_gives_target_minus_four_minus_four_until_end_of_turn(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = PoisonersApprentice(owner=p1, controller=p1)
        target = Creature(
            name="Target Bear",
            owner=p2,
            controller=p2,
            base_power=5,
            base_toughness=5,
        )
        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=[target])
        p1.life_gained_this_turn = 1
        p1._script.append(target)
        card.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=card, creature=card, controller=p1),
        )

        assert len(game.stack) == 1
        resolve_top(game)

        assert target.power == 1
        assert target.toughness == 1

        game.effect_manager.remove_expired(game)
        game.effect_manager.apply_all(game)

        assert target.power == 5
        assert target.toughness == 5

    def test_does_not_trigger_without_life_gain_this_turn(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = PoisonersApprentice(owner=p1, controller=p1)
        target = Creature(
            name="Target Bear",
            owner=p2,
            controller=p2,
            base_power=5,
            base_toughness=5,
        )
        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=[target])
        card.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=card, creature=card, controller=p1),
        )

        assert game.stack.is_empty()
        assert target.power == 5
        assert target.toughness == 5
