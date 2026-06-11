"""Tests for SOS 147 — Environmental Scientist."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_147.card_impl import EnvironmentalScientist
from benchmarks.sos.workspace.engine.casting import resolve_top
from benchmarks.sos.workspace.engine.card import Creature, Land
from benchmarks.sos.workspace.engine.events import EntersBattlefieldTriggeredEvent
from benchmarks.sos.workspace.engine.types import ManaCost, Supertype, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestEnvironmentalScientistProperties:
    """Static card data should match the SOS 147 spec."""

    def test_is_human_druid_creature(self) -> None:
        card = EnvironmentalScientist(owner=None)

        assert isinstance(card, Creature)
        assert "Human" in card.subtypes
        assert "Druid" in card.subtypes

    def test_name_cost_and_power_toughness(self) -> None:
        card = EnvironmentalScientist(owner=None)

        assert card.name == "Environmental Scientist"
        assert card.mana_cost == ManaCost.parse("{1}{G}")
        assert card.base_power == 2
        assert card.base_toughness == 2


class TestEnvironmentalScientistEntersTrigger:
    """Environmental Scientist should optionally find a basic land on entry."""

    def test_registers_an_enters_battlefield_trigger(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EnvironmentalScientist(owner=p1, controller=p1)

        card.register_triggers(game)

        triggers = game.trigger_manager.get_triggers_for_source(card)
        assert len(triggers) == 1
        assert triggers[0].event_type is EntersBattlefieldTriggeredEvent

    def test_when_it_enters_you_may_put_a_chosen_basic_land_from_your_library_into_your_hand(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EnvironmentalScientist(owner=p1, controller=p1)
        basic_land = Land(name="Forest", owner=p1, controller=p1, supertypes={Supertype.BASIC})
        nonbasic_land = Land(name="Campus", owner=p1, controller=p1)
        game.get_library(p1).add(nonbasic_land)
        game.get_library(p1).add(basic_land)
        set_board_state(game, 0, battlefield=[card])
        p1._script.extend([True, basic_land])
        card.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=card, creature=card, controller=p1),
        )

        assert len(game.stack) == 1
        resolve_top(game)

        assert game.get_hand(p1).contains(basic_land)
        assert not game.get_library(p1).contains(basic_land)
        assert game.get_library(p1).contains(nonbasic_land)

    def test_you_may_decline_the_search(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EnvironmentalScientist(owner=p1, controller=p1)
        basic_land = Land(name="Forest", owner=p1, controller=p1, supertypes={Supertype.BASIC})
        game.get_library(p1).add(basic_land)
        set_board_state(game, 0, battlefield=[card])
        p1._script.append(False)
        card.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=card, creature=card, controller=p1),
        )

        assert len(game.stack) == 1
        resolve_top(game)

        assert game.get_library(p1).contains(basic_land)
        assert not game.get_hand(p1).contains(basic_land)

    def test_search_records_the_public_reveal_and_shuffle_observations(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = EnvironmentalScientist(owner=p1, controller=p1)
        campus = Land(name="Campus", owner=p1, controller=p1)
        forest = Land(name="Forest", owner=p1, controller=p1, supertypes={Supertype.BASIC})
        grotto = Land(name="Crystal Grotto", owner=p1, controller=p1)
        game.get_library(p1).add(campus)
        game.get_library(p1).add(forest)
        game.get_library(p1).add(grotto)
        set_board_state(game, 0, battlefield=[card])
        game.shuffle_history.clear()
        game.queue_shuffle_order(grotto, campus)
        p1._script.extend([True, forest])
        card.register_triggers(game)

        game.trigger_manager.fire_event(
            game,
            EntersBattlefieldTriggeredEvent(permanent=card, creature=card, controller=p1),
        )

        resolve_top(game)

        assert len(game.reveal_history) == 1
        reveal_record = game.reveal_history[-1]
        assert reveal_record.player_index == 0
        assert reveal_record.cards == [forest]
        assert reveal_record.source is card
        assert reveal_record.reason == "Environmental Scientist enters"

        assert len(game.shuffle_history) == 1
        shuffle_record = game.shuffle_history[-1]
        assert shuffle_record.player_index == 0
        assert shuffle_record.zone is Zone.LIBRARY
        assert shuffle_record.before == [campus, grotto]
        assert shuffle_record.after == [grotto, campus]
        assert shuffle_record.source is card
        assert shuffle_record.reason == "Environmental Scientist search"
        assert shuffle_record.used_queued_order is True
        assert game.get_library(p1).get_all() == [grotto, campus]
