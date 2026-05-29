"""Tests for SOS 120 — Improvisation Capstone."""

from __future__ import annotations

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.card import Creature, Instant, Land, Sorcery
from engine.events import BeginningOfMainPhaseTriggeredEvent
from engine.stack import StackObject
from engine.types import Color, ManaCost, ManaType, Phase, Zone
from test_utils import cast_spell, create_game, set_board_state


class TestImprovisationCapstoneProperties:
    """Static card data should match the SOS 120 spec."""

    def test_is_red_sorcery_lesson_with_printed_cost(self) -> None:
        card = ImprovisationCapstone(owner=None)

        assert isinstance(card, Sorcery)
        assert card.name == "Improvisation Capstone"
        assert card.mana_cost == ManaCost.parse("{5}{R}{R}")
        assert card.colors == {Color.RED}
        assert "Lesson" in card.subtypes
        assert "Paradigm" in card.rules_text


class TestImprovisationCapstoneResolution:
    """Resolution should exile through mana value 4 and optionally free-cast spells."""

    @staticmethod
    def _creature(name: str, cost: str, *, power: int = 2, toughness: int = 2) -> Creature:
        return Creature(
            name=name,
            mana_cost=ManaCost.parse(cost),
            base_power=power,
            base_toughness=toughness,
        )

    @staticmethod
    def _instant(name: str, cost: str) -> Instant:
        return Instant(name=name, mana_cost=ManaCost.parse(cost))

    @staticmethod
    def _land(name: str) -> Land:
        return Land(name=name)

    @staticmethod
    def _load_library(player, cards: list[object]) -> None:
        library = player.zones[Zone.LIBRARY]
        for card in cards:
            card.owner = player
            card.controller = player
            library.add(card)

    def test_stops_after_the_first_exiled_card_with_mana_value_four_or_greater(self) -> None:
        game = create_game(scripts=([True], []))
        p1 = game.players[0]

        capstone = ImprovisationCapstone(owner=p1, controller=p1)
        below_threshold = self._instant("Still Studying", "{1}")
        capstone_hit = self._creature("Senior Project", "{4}", power=4, toughness=4)
        self._load_library(p1, [below_threshold, capstone_hit])
        set_board_state(
            game,
            0,
            hand=[capstone],
            mana={ManaType.COLORLESS: 5, ManaType.RED: 2},
        )

        cast_spell(game, 0, "Improvisation Capstone")

        assert game.get_battlefield(p1).contains(capstone_hit) is True
        assert game.get_library(p1).contains(below_threshold) is True
        assert game.get_exile(p1).contains(capstone) is True
        assert game.get_graveyard(p1).contains(capstone) is False

    def test_may_cast_only_some_of_the_exiled_spells_and_leaves_the_rest_in_exile(self) -> None:
        game = create_game(scripts=([True, False], []))
        p1 = game.players[0]

        capstone = ImprovisationCapstone(owner=p1, controller=p1)
        stays_in_library = self._instant("After Class", "{1}")
        declined_spell = self._instant("Optional Reading", "{3}")
        cast_spell_card = self._creature("Quick Study", "{1}", power=1, toughness=1)
        exiled_land = self._land("Campus")
        self._load_library(
            p1,
            [stays_in_library, declined_spell, cast_spell_card, exiled_land],
        )
        set_board_state(
            game,
            0,
            hand=[capstone],
            mana={ManaType.COLORLESS: 5, ManaType.RED: 2},
        )

        cast_spell(game, 0, "Improvisation Capstone")

        assert game.get_battlefield(p1).contains(cast_spell_card) is True
        assert game.get_exile(p1).contains(declined_spell) is True
        assert game.get_exile(p1).contains(exiled_land) is True
        assert game.get_library(p1).contains(stays_in_library) is True
        assert game.get_exile(p1).contains(capstone) is True

    def test_exiles_all_remaining_cards_if_library_runs_out_before_total_four(self) -> None:
        game = create_game(scripts=([True, True], []))
        p1 = game.players[0]

        capstone = ImprovisationCapstone(owner=p1, controller=p1)
        instant_card = self._instant("Short Syllabus", "{1}")
        creature_card = self._creature("Lab Partner", "{2}")
        land_card = self._land("Practice Field")
        self._load_library(p1, [instant_card, creature_card, land_card])
        set_board_state(
            game,
            0,
            hand=[capstone],
            mana={ManaType.COLORLESS: 5, ManaType.RED: 2},
        )

        cast_spell(game, 0, "Improvisation Capstone")

        assert game.get_library(p1).get_all() == []
        assert game.get_graveyard(p1).contains(instant_card) is True
        assert game.get_battlefield(p1).contains(creature_card) is True
        assert game.get_exile(p1).contains(land_card) is True
        assert game.get_exile(p1).contains(capstone) is True


class TestImprovisationCapstoneParadigm:
    """Paradigm should exile the spell and offer a copy on your first main phases."""

    def test_paradigm_exiles_the_spell_and_lets_your_first_main_phase_cast_a_copy(self) -> None:
        game = create_game(scripts=([True], []))
        p1 = game.players[0]

        capstone = ImprovisationCapstone(owner=p1, controller=p1)
        set_board_state(
            game,
            0,
            hand=[capstone],
            mana={ManaType.COLORLESS: 5, ManaType.RED: 2},
        )

        cast_spell(game, 0, "Improvisation Capstone")

        assert game.get_exile(p1).contains(capstone) is True
        assert game.get_graveyard(p1).contains(capstone) is False

        game.trigger_manager.fire_event(
            game,
            BeginningOfMainPhaseTriggeredEvent(
                player=p1,
                phase=Phase.PRECOMBAT_MAIN,
            ),
        )

        assert len(game.stack.objects()) == 1
        trigger = game.stack.pop()
        trigger.on_resolve(game)

        assert len(game.stack.objects()) == 1
        copy_obj = game.stack.peek()
        assert isinstance(copy_obj, StackObject)
        assert copy_obj.source is not capstone
        assert copy_obj.controller is p1
        assert copy_obj.source.name == "Improvisation Capstone"
        assert game.get_exile(p1).contains(capstone) is True

    def test_paradigm_does_not_trigger_during_an_opponents_or_postcombat_main_phase(self) -> None:
        game = create_game()
        p1, p2 = game.players

        capstone = ImprovisationCapstone(owner=p1, controller=p1)
        set_board_state(
            game,
            0,
            hand=[capstone],
            mana={ManaType.COLORLESS: 5, ManaType.RED: 2},
        )

        cast_spell(game, 0, "Improvisation Capstone")

        game.trigger_manager.fire_event(
            game,
            BeginningOfMainPhaseTriggeredEvent(
                player=p2,
                phase=Phase.PRECOMBAT_MAIN,
            ),
        )
        assert game.stack.is_empty()

        game.trigger_manager.fire_event(
            game,
            BeginningOfMainPhaseTriggeredEvent(
                player=p1,
                phase=Phase.POSTCOMBAT_MAIN,
            ),
        )
        assert game.stack.is_empty()

        game.trigger_manager.fire_event(
            game,
            BeginningOfMainPhaseTriggeredEvent(
                player=p1,
                phase=Phase.PRECOMBAT_MAIN,
            ),
        )
        assert len(game.stack.objects()) == 1
