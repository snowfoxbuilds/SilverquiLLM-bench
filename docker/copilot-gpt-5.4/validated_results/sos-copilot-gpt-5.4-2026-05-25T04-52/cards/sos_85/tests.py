"""Tests for SOS 85 — Grave Researcher // Reanimate."""

from __future__ import annotations

import pytest

from benchmarks.sos.workspace.cards.sos.sos_85.card_impl import GraveResearcherReanimate
from benchmarks.sos.workspace.engine.casting import CastingError, resolve_top
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Sorcery
from benchmarks.sos.workspace.engine.events import BeginningOfUpkeepTriggeredEvent
from benchmarks.sos.workspace.engine.types import ManaCost
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestGraveResearcherReanimateProperties:
    """Static front-face data should match the SOS 85 spec."""

    def test_is_troll_warlock_creature(self) -> None:
        card = GraveResearcherReanimate(owner=None)
        assert isinstance(card, Creature)
        assert "Troll" in card.subtypes
        assert "Warlock" in card.subtypes

    def test_front_face_name_cost_and_power_toughness(self) -> None:
        card = GraveResearcherReanimate(owner=None)
        assert card.name == "Grave Researcher"
        assert card.mana_cost == ManaCost.parse("{2}{B}")
        assert card.base_power == 3
        assert card.base_toughness == 3


class TestGraveResearcherReanimateUpkeep:
    """Grave Researcher should surveil on upkeep and prepare at threshold."""

    def test_registers_a_beginning_of_upkeep_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = GraveResearcherReanimate(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is BeginningOfUpkeepTriggeredEvent

    def test_does_not_trigger_on_an_opponents_upkeep(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = GraveResearcherReanimate(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.register_triggers(game)
        game.active_player_index = 1

        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        assert game.stack.is_empty()

    def test_your_upkeep_can_surveil_a_creature_into_your_graveyard_and_then_prepare_itself(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = GraveResearcherReanimate(owner=p1, controller=p1)
        first_creature = Creature(
            name="First Creature",
            owner=p1,
            controller=p1,
            base_power=1,
            base_toughness=1,
        )
        second_creature = Creature(
            name="Second Creature",
            owner=p1,
            controller=p1,
            base_power=1,
            base_toughness=1,
        )
        surveilled_creature = Creature(
            name="Surveilled Creature",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 0, battlefield=[card], graveyard=[first_creature, second_creature])
        game.get_library(p1).add(surveilled_creature)
        p1._script.append(True)
        card.register_triggers(game)
        game.active_player_index = 0

        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())

        assert len(game.stack) == 1

        resolve_top(game)

        assert game.get_graveyard(p1).contains(surveilled_creature)
        assert not game.get_library(p1).contains(surveilled_creature)
        assert card.is_prepared is True

    def test_your_upkeep_does_not_prepare_it_when_you_still_have_fewer_than_three_creature_cards_in_graveyard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = GraveResearcherReanimate(owner=p1, controller=p1)
        first_creature = Creature(
            name="First Creature",
            owner=p1,
            controller=p1,
            base_power=1,
            base_toughness=1,
        )
        second_creature = Creature(
            name="Second Creature",
            owner=p1,
            controller=p1,
            base_power=1,
            base_toughness=1,
        )
        top_creature = Creature(
            name="Top Creature",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 0, battlefield=[card], graveyard=[first_creature, second_creature])
        game.get_library(p1).add(top_creature)
        p1._script.append(False)
        card.register_triggers(game)
        game.active_player_index = 0

        game.trigger_manager.fire_event(game, BeginningOfUpkeepTriggeredEvent())
        resolve_top(game)

        assert game.get_library(p1).contains(top_creature)
        assert not game.get_graveyard(p1).contains(top_creature)
        assert card.is_prepared is False


class TestGraveResearcherReanimatePrepared:
    """Grave Researcher should cast Reanimate copies while prepared."""

    def test_prepared_spell_copy_is_reanimate_and_unprepares_the_card(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = GraveResearcherReanimate(owner=p1, controller=p1)
        set_board_state(game, 0, battlefield=[card])
        card.become_prepared()

        stack_obj = card.cast_prepared_spell_copy(game)

        assert card.is_prepared is False
        assert stack_obj.source.name == "Reanimate"
        assert isinstance(stack_obj.source, Sorcery)
        assert stack_obj.source.mana_cost == ManaCost.parse("{B}")
        assert stack_obj.source.controller is p1
        assert getattr(stack_obj.source, "prepared_source", None) is card

    def test_cannot_cast_prepared_spell_copy_while_unprepared(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = GraveResearcherReanimate(owner=p1, controller=p1)

        with pytest.raises(CastingError, match="not prepared"):
            card.cast_prepared_spell_copy(game)
