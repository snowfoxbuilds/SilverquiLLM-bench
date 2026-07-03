"""Tests for SOS 171 — Abstract Paintmage."""

from __future__ import annotations

import pytest

from benchmarks.sos.workspace.cards.sos.sos_171.card_impl import AbstractPaintmage
from benchmarks.sos.workspace.engine.casting import CastingError, cast_spell as cast_spell_paid, resolve_top
from benchmarks.sos.workspace.engine.card import Creature, Instant
from benchmarks.sos.workspace.engine.events import BeginningOfFirstMainPhaseTriggeredEvent
from benchmarks.sos.workspace.engine.types import ManaCost, ManaType, Phase
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestAbstractPaintmageProperties:
    """Static card data should match the SOS 171 spec."""

    def test_is_djinn_sorcerer_creature(self) -> None:
        card = AbstractPaintmage(owner=None)

        assert isinstance(card, Creature)
        assert "Djinn" in card.subtypes
        assert "Sorcerer" in card.subtypes

    def test_name_cost_and_power_toughness(self) -> None:
        card = AbstractPaintmage(owner=None)

        assert card.name == "Abstract Paintmage"
        assert card.mana_cost == ManaCost.parse("{U}{U/R}{R}")
        assert card.base_power == 2
        assert card.base_toughness == 2


class TestAbstractPaintmageFirstMainPhaseTrigger:
    """Abstract Paintmage should make restricted mana at your first main phase."""

    def test_registers_a_beginning_of_first_main_phase_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = AbstractPaintmage(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is BeginningOfFirstMainPhaseTriggeredEvent

    def test_your_first_main_phase_puts_a_trigger_on_the_stack_and_adds_blue_and_red_mana(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        card = AbstractPaintmage(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)

        game.trigger_manager.fire_event(game, BeginningOfFirstMainPhaseTriggeredEvent(player=p1))

        assert len(game.stack) == 1

        resolve_top(game)

        assert p1.mana_pool.get(ManaType.BLUE) == 1
        assert p1.mana_pool.get(ManaType.RED) == 1
        assert p1.mana_pool.total() == 2

    def test_triggered_mana_cannot_be_spent_to_cast_a_creature_spell(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        paintmage = AbstractPaintmage(owner=p1, controller=p1)
        creature_spell = Creature(
            name="Lecture Hall Cub",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{U}"),
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 0, battlefield=[paintmage], hand=[creature_spell])
        paintmage.register_triggers(game)

        game.trigger_manager.fire_event(game, BeginningOfFirstMainPhaseTriggeredEvent(player=p1))
        resolve_top(game)

        with pytest.raises(CastingError, match="insufficient mana"):
            cast_spell_paid(game, p1, creature_spell)

        assert game.get_hand(p1).contains(creature_spell)
        assert p1.mana_pool.get(ManaType.BLUE) == 1
        assert p1.mana_pool.get(ManaType.RED) == 1

    def test_triggered_mana_can_be_spent_to_cast_an_instant_spell(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        paintmage = AbstractPaintmage(owner=p1, controller=p1)
        spell = Instant(
            name="Chromatic Insight",
            owner=p1,
            controller=p1,
            mana_cost=ManaCost.parse("{U}{R}"),
        )
        set_board_state(game, 0, battlefield=[paintmage], hand=[spell])
        paintmage.register_triggers(game)

        game.trigger_manager.fire_event(game, BeginningOfFirstMainPhaseTriggeredEvent(player=p1))
        resolve_top(game)

        cast_spell_paid(game, p1, spell)

        assert game.stack.peek().source is spell
        assert p1.mana_pool.total() == 0
