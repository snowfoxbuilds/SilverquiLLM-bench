"""Tests for SOS 120 — Improvisation Capstone."""

from __future__ import annotations

from typing import Any

from benchmarks.sos.workspace.cards.sos.sos_120.card_impl import ImprovisationCapstone
from benchmarks.sos.workspace.engine.casting import (
    can_cast_paradigm_copy,
    cast_paradigm_copy,
    cast_spell as cast_spell_paid,
    get_scheduled_paradigm_cards,
    resolve_top,
)
from benchmarks.sos.workspace.engine.card import CardImpl, Sorcery
from benchmarks.sos.workspace.engine.types import ManaCost, ManaType, Phase
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class OneManaNote(Sorcery):
    """Simple one-mana sorcery used to validate exile thresholds."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "One Mana Note")
        kwargs.setdefault("mana_cost", ManaCost.parse("{1}"))
        super().__init__(**kwargs)


class ThreeManaLesson(Sorcery):
    """Simple three-mana sorcery used to validate exile thresholds."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Three Mana Lesson")
        kwargs.setdefault("mana_cost", ManaCost.parse("{3}"))
        kwargs.setdefault("subtypes", {"Lesson"})
        super().__init__(**kwargs)


class FourManaLesson(Sorcery):
    """Simple four-mana sorcery used to validate free casting from exile."""

    def __init__(self, resolved: list[str] | None = None, **kwargs: Any) -> None:
        kwargs.setdefault("name", "Four Mana Lesson")
        kwargs.setdefault("mana_cost", ManaCost.parse("{4}"))
        kwargs.setdefault("subtypes", {"Lesson"})
        super().__init__(**kwargs)
        self._resolved = resolved if resolved is not None else []

    def on_resolve(self, game) -> None:  # noqa: ANN001, ARG002
        self._resolved.append(self.name)


class TestImprovisationCapstoneProperties:
    """Static card data should match the SOS 120 spec."""

    def test_is_lesson_sorcery_with_paradigm(self) -> None:
        card = ImprovisationCapstone(owner=None)

        assert isinstance(card, Sorcery)
        assert "Lesson" in card.subtypes
        assert getattr(card, "paradigm_enabled", False) is True

    def test_name_and_mana_cost(self) -> None:
        card = ImprovisationCapstone(owner=None)

        assert card.name == "Improvisation Capstone"
        assert card.mana_cost == ManaCost.parse("{5}{R}{R}")


class TestImprovisationCapstoneResolution:
    """Improvisation Capstone should exile up to the threshold and support paradigm."""

    def test_on_resolve_exiles_cards_from_the_top_of_your_library_until_total_mana_value_is_four_or_more(self) -> None:
        game = create_game()
        p1 = game.players[0]
        bottom = CardImpl(name="Library Bottom", owner=p1, controller=p1)
        one_drop = OneManaNote(owner=p1, controller=p1)
        three_drop = ThreeManaLesson(owner=p1, controller=p1)
        game.get_library(p1).add(bottom)
        game.get_library(p1).add(three_drop)
        game.get_library(p1).add(one_drop)
        p1._script.extend([False, False, False])

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        spell.on_resolve(game)

        assert game.get_exile(p1).contains(one_drop)
        assert game.get_exile(p1).contains(three_drop)
        assert not game.get_library(p1).contains(one_drop)
        assert not game.get_library(p1).contains(three_drop)
        assert game.get_library(p1).contains(bottom)

    def test_on_resolve_can_cast_any_number_of_exiled_spells_without_paying_their_mana_costs(self) -> None:
        game = create_game()
        p1 = game.players[0]
        resolved: list[str] = []
        one_drop = OneManaNote(owner=p1, controller=p1)
        three_drop = ThreeManaLesson(owner=p1, controller=p1)
        four_drop = FourManaLesson(owner=p1, controller=p1, resolved=resolved)
        game.get_library(p1).add(four_drop)
        game.get_library(p1).add(three_drop)
        game.get_library(p1).add(one_drop)
        p1._script.extend([True, one_drop, True, three_drop, False])

        spell = ImprovisationCapstone(owner=p1, controller=p1)
        spell.on_resolve(game)

        assert len(game.stack) == 2
        resolve_top(game)
        resolve_top(game)

        assert not game.get_exile(p1).contains(one_drop)
        assert not game.get_exile(p1).contains(three_drop)
        assert game.get_graveyard(p1).contains(one_drop)
        assert game.get_graveyard(p1).contains(three_drop)
        assert resolved == []

    def test_paid_cast_exiles_itself_schedules_future_paradigm_copies_and_exiles_library_cards_to_the_threshold(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.active_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        lesson = FourManaLesson(owner=p1, controller=p1)
        spell = ImprovisationCapstone(owner=p1, controller=p1)
        game.get_library(p1).add(lesson)
        set_board_state(game, 0, hand=[spell], mana={ManaType.RED: 7})
        p1._script.extend([False, False])

        cast_spell_paid(game, p1, spell)
        resolve_top(game)

        assert game.get_exile(p1).contains(lesson)
        assert game.get_exile(p1).contains(spell)
        assert get_scheduled_paradigm_cards(game, p1) == [spell]
        assert can_cast_paradigm_copy(game, p1, spell) is True

    def test_casting_a_paradigm_copy_keeps_the_source_exiled_and_repeats_the_exile_effect(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.active_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        first_lesson = FourManaLesson(owner=p1, controller=p1)
        second_lesson = FourManaLesson(owner=p1, controller=p1)
        spell = ImprovisationCapstone(owner=p1, controller=p1)
        game.get_library(p1).add(first_lesson)
        set_board_state(game, 0, hand=[spell], mana={ManaType.RED: 7})
        p1._script.extend([False, False])

        cast_spell_paid(game, p1, spell)
        resolve_top(game)

        game.get_library(p1).add(second_lesson)
        p1._script.extend([True, second_lesson, False])

        stack_obj = cast_paradigm_copy(game, p1, spell)

        assert stack_obj.source is not spell
        assert getattr(stack_obj.source, "paradigm_source", None) is spell

        resolve_top(game)

        assert game.get_exile(p1).contains(spell)
        assert get_scheduled_paradigm_cards(game, p1) == [spell]
        assert len(game.stack) == 1
        assert game.stack.peek().source is second_lesson
