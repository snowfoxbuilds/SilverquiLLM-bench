"""Tests for SOS 120 — Improvisation Capstone."""

from __future__ import annotations

from cards.sos.sos_120.card_impl import ImprovisationCapstone
from engine.casting import cast_spell as engine_cast_spell
from engine.card import Creature, Instant, Land, Sorcery
from engine.types import CardType, ManaCost, ManaType, Phase, Step, Zone
from test_utils import create_game, set_board_state


class PracticeBurst(Instant):
    """Cheap spell used to validate free-casting from exile."""

    def __init__(self) -> None:
        super().__init__(name="Practice Burst", mana_cost=ManaCost.parse("{1}{R}"))
        self.was_resolved = False

    def on_resolve(self, game) -> None:
        self.was_resolved = True


class StudioApprentice(Creature):
    """Cheap creature spell used to validate free-casting permanents."""

    def __init__(self) -> None:
        super().__init__(
            name="Studio Apprentice",
            mana_cost=ManaCost.parse("{1}{R}"),
            base_power=2,
            base_toughness=2,
        )


class LectureNotes(Land):
    """A non-spell card that can be exiled but not cast."""

    def __init__(self) -> None:
        super().__init__(name="Lecture Notes")


class FinalProject(Sorcery):
    """Expensive spell kept deeper in the library to prove the reveal stops."""

    def __init__(self) -> None:
        super().__init__(name="Final Project", mana_cost=ManaCost.parse("{5}{R}"))


def _set_library_bottom_to_top(player, cards) -> None:
    library = player.zones[Zone.LIBRARY]
    for existing in list(library.get_all()):
        library.remove(existing)
    for card in cards:
        card.owner = player
        card.controller = player
        library.add(card)


def _resolve_top_of_stack(game) -> None:
    stack_obj = game.stack.pop()
    stack_obj.on_resolve(game)


def _resolve_entire_stack(game) -> None:
    while not game.stack.is_empty():
        _resolve_top_of_stack(game)


def _advance_to(
    game,
    *,
    active_player_index: int,
    phase: Phase,
    step: Step | None,
) -> None:
    for _ in range(30):
        if (
            game.active_player_index == active_player_index
            and game.phase == phase
            and game.step == step
        ):
            return
        game.advance_phase()
    raise AssertionError(
        f"Did not reach active={active_player_index}, phase={phase}, step={step}"
    )


def _cast_and_resolve_capstone_once(game, player, capstone) -> None:
    game.active_player_index = 0
    game.priority_player_index = 0
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    engine_cast_spell(game, player, capstone)
    _resolve_top_of_stack(game)


class TestImprovisationCapstoneProperties:
    """Static card data should match the SOS 120 spec."""

    def test_is_a_lesson_sorcery(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert isinstance(card, Sorcery)
        assert CardType.SORCERY in card.card_types
        assert "Lesson" in card.subtypes

    def test_name_and_mana_cost(self) -> None:
        card = ImprovisationCapstone(owner=None)
        assert card.name == "Improvisation Capstone"
        assert card.mana_cost == ManaCost.parse("{5}{R}{R}")


class TestImprovisationCapstoneResolution:
    """Resolution should exile until mana value 4+ and optionally free-cast spells."""

    def test_exiles_from_the_top_until_total_mana_value_four_or_greater_and_stops(self) -> None:
        game = create_game(scripts=([False, False], []))
        p1 = game.players[0]
        capstone = ImprovisationCapstone(owner=p1, controller=p1)
        burst = PracticeBurst()
        notes = LectureNotes()
        apprentice = StudioApprentice()
        leftover = FinalProject()

        set_board_state(
            game,
            0,
            hand=[capstone],
            mana={ManaType.RED: 2, ManaType.COLORLESS: 5},
        )
        _set_library_bottom_to_top(p1, [leftover, apprentice, notes, burst])

        _cast_and_resolve_capstone_once(game, p1, capstone)

        exile = game.get_exile(p1)
        library = game.get_library(p1)

        assert exile.contains(burst)
        assert exile.contains(notes)
        assert exile.contains(apprentice)
        assert library.contains(leftover)
        assert not exile.contains(leftover)
        assert game.stack.is_empty()

    def test_may_free_cast_any_number_of_exiled_spells_without_casting_exiled_lands(self) -> None:
        game = create_game(scripts=([True, True], []))
        p1 = game.players[0]
        capstone = ImprovisationCapstone(owner=p1, controller=p1)
        burst = PracticeBurst()
        notes = LectureNotes()
        apprentice = StudioApprentice()
        leftover = FinalProject()

        set_board_state(
            game,
            0,
            hand=[capstone],
            mana={ManaType.RED: 2, ManaType.COLORLESS: 5},
        )
        _set_library_bottom_to_top(p1, [leftover, apprentice, notes, burst])

        _cast_and_resolve_capstone_once(game, p1, capstone)

        stack_sources = {obj.source for obj in game.stack.objects()}
        assert stack_sources == {burst, apprentice}
        assert game.get_exile(p1).contains(notes)
        assert not game.get_exile(p1).contains(burst)
        assert not game.get_exile(p1).contains(apprentice)
        assert game.get_library(p1).contains(leftover)

        _resolve_entire_stack(game)

        assert burst.was_resolved is True
        assert game.get_graveyard(p1).contains(burst)
        assert game.get_battlefield(p1).contains(apprentice)
        assert game.get_exile(p1).contains(notes)
        assert game.players[0].mana_pool.total() == 0


class TestImprovisationCapstoneParadigm:
    """Paradigm should exile the spell and create recurring copy-cast windows."""

    def test_paradigm_exiles_the_spell_even_with_an_empty_library(self) -> None:
        game = create_game()
        p1 = game.players[0]
        capstone = ImprovisationCapstone(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            hand=[capstone],
            mana={ManaType.RED: 2, ManaType.COLORLESS: 5},
        )

        _cast_and_resolve_capstone_once(game, p1, capstone)

        assert game.get_exile(p1).contains(capstone)
        assert not game.get_graveyard(p1).contains(capstone)
        assert game.stack.is_empty()

    def test_paradigm_casts_a_copy_on_your_next_precombat_main_but_not_on_your_opponents(self) -> None:
        game = create_game(scripts=([True], []))
        p1 = game.players[0]
        capstone = ImprovisationCapstone(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            hand=[capstone],
            mana={ManaType.RED: 2, ManaType.COLORLESS: 5},
        )

        _cast_and_resolve_capstone_once(game, p1, capstone)

        _advance_to(game, active_player_index=1, phase=Phase.PRECOMBAT_MAIN, step=None)
        assert game.stack.is_empty()

        _advance_to(game, active_player_index=0, phase=Phase.PRECOMBAT_MAIN, step=None)

        copy_obj = game.stack.peek()
        assert copy_obj is not None
        assert copy_obj.source is not capstone
        assert copy_obj.source.name == capstone.name
        assert game.get_exile(p1).contains(capstone)

    def test_paradigm_keeps_offering_a_copy_on_later_precombat_main_phases(self) -> None:
        game = create_game(scripts=([True, True], []))
        p1 = game.players[0]
        capstone = ImprovisationCapstone(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            hand=[capstone],
            mana={ManaType.RED: 2, ManaType.COLORLESS: 5},
        )

        _cast_and_resolve_capstone_once(game, p1, capstone)

        _advance_to(game, active_player_index=1, phase=Phase.PRECOMBAT_MAIN, step=None)
        _advance_to(game, active_player_index=0, phase=Phase.PRECOMBAT_MAIN, step=None)
        assert len(game.stack.objects()) == 1
        first_copy = game.stack.peek()
        assert first_copy is not None
        assert first_copy.source.name == capstone.name
        _resolve_entire_stack(game)
        assert game.get_exile(p1).contains(capstone)

        _advance_to(game, active_player_index=1, phase=Phase.PRECOMBAT_MAIN, step=None)
        _advance_to(game, active_player_index=0, phase=Phase.PRECOMBAT_MAIN, step=None)
        assert len(game.stack.objects()) == 1
        second_copy = game.stack.peek()
        assert second_copy is not None
        assert second_copy.source is not capstone
        assert second_copy.source.name == capstone.name
