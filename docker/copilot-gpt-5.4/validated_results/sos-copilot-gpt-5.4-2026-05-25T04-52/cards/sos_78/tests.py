"""Tests for SOS 78 — Decorum Dissertation."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_78.card_impl import DecorumDissertation
from benchmarks.sos.workspace.engine.casting import (
    can_cast_paradigm_copy,
    cast_paradigm_copy,
    cast_spell as cast_spell_paid,
    get_scheduled_paradigm_cards,
    resolve_top,
)
from benchmarks.sos.workspace.engine.card import CardImpl, Sorcery
from benchmarks.sos.workspace.engine.types import ManaCost, ManaType, Phase, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestDecorumDissertationProperties:
    """Static card data should match the SOS 78 spec."""

    def test_is_lesson_sorcery(self) -> None:
        card = DecorumDissertation(owner=None)
        assert isinstance(card, Sorcery)
        assert "Lesson" in card.subtypes

    def test_name_and_mana_cost(self) -> None:
        card = DecorumDissertation(owner=None)
        assert card.name == "Decorum Dissertation"
        assert card.mana_cost == ManaCost.parse("{3}{B}{B}")


class TestDecorumDissertationTargeting:
    """Decorum Dissertation should target a single player."""

    def test_returns_single_player_target_requirement(self) -> None:
        game = create_game()
        reqs = DecorumDissertation(owner=None).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.BATTLEFIELD

    def test_target_filter_accepts_players_and_rejects_non_players(self) -> None:
        game = create_game()
        p1 = game.players[0]
        req = DecorumDissertation(owner=p1, controller=p1).get_targets(game)[0]
        non_player = CardImpl(name="Lecture Notes", owner=p1, controller=p1)

        assert req.filter_fn(game.players[0]) is True
        assert req.filter_fn(game.players[1]) is True
        assert req.filter_fn(non_player) is False


class TestDecorumDissertationResolution:
    """Decorum Dissertation should draw, drain, and support paradigm recasts."""

    def test_on_resolve_target_player_draws_two_and_loses_two_life(self) -> None:
        game = create_game()
        p1, p2 = game.players
        draw_one = CardImpl(name="First Lesson", owner=p2, controller=p2)
        draw_two = CardImpl(name="Second Lesson", owner=p2, controller=p2)
        game.get_library(p2).add(draw_one)
        game.get_library(p2).add(draw_two)

        spell = DecorumDissertation(owner=p1, controller=p1)
        spell.chosen_targets = [p2]
        spell.on_resolve(game)

        assert game.get_hand(p2).contains(draw_one)
        assert game.get_hand(p2).contains(draw_two)
        assert p2.life == 18

    def test_paid_cast_exiles_itself_schedules_future_paradigm_copies_and_resolves_its_effect(self) -> None:
        game = create_game()
        p1, p2 = game.players
        game.active_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        draw_one = CardImpl(name="First Lesson", owner=p2, controller=p2)
        draw_two = CardImpl(name="Second Lesson", owner=p2, controller=p2)
        spell = DecorumDissertation(owner=p1, controller=p1)

        game.get_library(p2).add(draw_one)
        game.get_library(p2).add(draw_two)
        set_board_state(game, 0, hand=[spell], mana={ManaType.BLACK: 5})
        p1._script.append(p2)

        cast_spell_paid(game, p1, spell)
        resolve_top(game)

        assert game.get_hand(p2).contains(draw_one)
        assert game.get_hand(p2).contains(draw_two)
        assert p2.life == 18
        assert game.get_exile(p1).contains(spell)
        assert get_scheduled_paradigm_cards(game, p1) == [spell]
        assert can_cast_paradigm_copy(game, p1, spell) is True

    def test_casting_a_paradigm_copy_keeps_the_source_exiled_and_repeats_the_effect(self) -> None:
        game = create_game()
        p1, p2 = game.players
        game.active_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        first_draw = CardImpl(name="First Lesson", owner=p2, controller=p2)
        second_draw = CardImpl(name="Second Lesson", owner=p2, controller=p2)
        third_draw = CardImpl(name="Third Lesson", owner=p2, controller=p2)
        fourth_draw = CardImpl(name="Fourth Lesson", owner=p2, controller=p2)
        spell = DecorumDissertation(owner=p1, controller=p1)

        game.get_library(p2).add(first_draw)
        game.get_library(p2).add(second_draw)
        set_board_state(game, 0, hand=[spell], mana={ManaType.BLACK: 5})
        p1._script.append(p2)
        cast_spell_paid(game, p1, spell)
        resolve_top(game)

        game.get_library(p2).add(third_draw)
        game.get_library(p2).add(fourth_draw)
        p1._script.append(p2)

        stack_obj = cast_paradigm_copy(game, p1, spell)

        assert stack_obj.source is not spell
        assert getattr(stack_obj.source, "paradigm_source", None) is spell

        resolve_top(game)

        assert game.get_hand(p2).contains(third_draw)
        assert game.get_hand(p2).contains(fourth_draw)
        assert p2.life == 16
        assert game.get_exile(p1).contains(spell)
        assert get_scheduled_paradigm_cards(game, p1) == [spell]
        assert can_cast_paradigm_copy(game, p1, spell) is True
