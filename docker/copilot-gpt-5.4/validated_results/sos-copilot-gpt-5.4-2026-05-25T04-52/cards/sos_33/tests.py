"""Tests for SOS 33 — Spiritcall Enthusiast // Scrollboost."""

from __future__ import annotations

import pytest

from benchmarks.sos.workspace.cards.sos.sos_33.card_impl import SpiritcallEnthusiastScrollboost
from benchmarks.sos.workspace.engine.casting import CastingError, resolve_top
from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.events import EntersBattlefieldTriggeredEvent
from benchmarks.sos.workspace.engine.types import ManaCost, Phase
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestSpiritcallEnthusiastScrollboostProperties:
    """Static front-face data should match the SOS 33 spec."""

    def test_is_cat_cleric_creature(self) -> None:
        card = SpiritcallEnthusiastScrollboost(owner=None)
        assert isinstance(card, Creature)
        assert "Cat" in card.subtypes
        assert "Cleric" in card.subtypes

    def test_front_face_name_cost_and_power_toughness(self) -> None:
        card = SpiritcallEnthusiastScrollboost(owner=None)
        assert card.name == "Spiritcall Enthusiast"
        assert card.mana_cost == ManaCost.parse("{2}{W}")
        assert card.base_power == 3
        assert card.base_toughness == 3


class TestSpiritcallEnthusiastScrollboostPrepared:
    """Spiritcall Enthusiast should prepare itself when your tokens enter."""

    def test_registers_an_enters_battlefield_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SpiritcallEnthusiastScrollboost(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is EntersBattlefieldTriggeredEvent

    def test_your_token_entering_puts_a_trigger_on_the_stack_and_prepares_the_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SpiritcallEnthusiastScrollboost(owner=p1, controller=p1)
        token = Creature(name="Inkling", owner=p1, controller=p1, base_power=1, base_toughness=1)
        token.is_token = True
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)
        game.get_battlefield(p1).add(token)

        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=token, creature=token, controller=p1),
        )

        assert len(game.stack) == 1
        assert game.stack.peek().source is card

        resolve_top(game)

        assert card.is_prepared is True

    def test_nontoken_entry_does_not_trigger_preparation(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SpiritcallEnthusiastScrollboost(owner=p1, controller=p1)
        creature = Creature(name="Helpful Bear", owner=p1, controller=p1, base_power=2, base_toughness=2)
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)
        game.get_battlefield(p1).add(creature)

        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=creature, creature=creature, controller=p1),
        )

        assert game.stack.is_empty()
        assert card.is_prepared is False

    def test_opponents_token_entry_does_not_trigger_preparation(self) -> None:
        game = create_game()
        p1, p2 = game.players
        card = SpiritcallEnthusiastScrollboost(owner=p1, controller=p1)
        token = Creature(name="Enemy Inkling", owner=p2, controller=p2, base_power=1, base_toughness=1)
        token.is_token = True
        set_board_state(game, 0, battlefield=[card])
        set_board_state(game, 1, battlefield=[token])
        card.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=token, creature=token, controller=p2),
        )

        assert game.stack.is_empty()
        assert card.is_prepared is False

    def test_prepared_spell_copy_is_scrollboost_and_unprepares_the_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        card = SpiritcallEnthusiastScrollboost(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.become_prepared()

        stack_obj = card.cast_prepared_spell_copy(game)

        assert card.is_prepared is False
        assert stack_obj.source.name == "Scrollboost"
        assert isinstance(stack_obj.source, Sorcery)
        assert stack_obj.source.mana_cost == ManaCost.parse("{1}{W}")
        assert stack_obj.source.controller is p1
        assert getattr(stack_obj.source, "prepared_source", None) is card

    def test_cannot_cast_prepared_spell_copy_while_unprepared(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = SpiritcallEnthusiastScrollboost(owner=p1, controller=p1)

        with pytest.raises(CastingError, match="not prepared"):
            card.cast_prepared_spell_copy(game)
