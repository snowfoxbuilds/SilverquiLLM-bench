"""Tests for SOS 149 — Germination Practicum."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_149.card_impl import GerminationPracticum
from benchmarks.sos.workspace.engine.casting import (
    can_cast_paradigm_copy,
    cast_paradigm_copy,
    cast_spell as cast_spell_paid,
    get_scheduled_paradigm_cards,
    resolve_top,
)
from benchmarks.sos.workspace.engine.card import Creature, Sorcery
from benchmarks.sos.workspace.engine.types import ManaCost, ManaType, Phase
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestGerminationPracticumProperties:
    """Static card data should match the SOS 149 spec."""

    def test_is_lesson_sorcery_with_paradigm(self) -> None:
        card = GerminationPracticum(owner=None)

        assert isinstance(card, Sorcery)
        assert "Lesson" in card.subtypes
        assert getattr(card, "paradigm_enabled", False) is True

    def test_name_and_mana_cost(self) -> None:
        card = GerminationPracticum(owner=None)

        assert card.name == "Germination Practicum"
        assert card.mana_cost == ManaCost.parse("{3}{G}{G}")


class TestGerminationPracticumResolution:
    """Germination Practicum should grow your team and support paradigm recasts."""

    def test_on_resolve_puts_two_plus_one_plus_one_counters_on_each_creature_you_control_only(self) -> None:
        game = create_game()
        p1, p2 = game.players
        first_ally = Creature(
            name="First Ally",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        second_ally = Creature(
            name="Second Ally",
            owner=p1,
            controller=p1,
            base_power=1,
            base_toughness=3,
        )
        opposing_creature = Creature(
            name="Opposing Creature",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        set_board_state(game, 0, battlefield=[first_ally, second_ally])
        set_board_state(game, 1, battlefield=[opposing_creature])

        spell = GerminationPracticum(owner=p1, controller=p1)
        spell.on_resolve(game)

        assert first_ally.plus_one_counters == 2
        assert first_ally.power == 4
        assert first_ally.toughness == 4
        assert second_ally.plus_one_counters == 2
        assert second_ally.power == 3
        assert second_ally.toughness == 5
        assert opposing_creature.plus_one_counters == 0

    def test_paid_cast_exiles_itself_schedules_future_paradigm_copies_and_buffs_your_team(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.active_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        target = Creature(
            name="Team Student",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        spell = GerminationPracticum(owner=p1, controller=p1)
        set_board_state(
            game,
            0,
            battlefield=[target],
            hand=[spell],
            mana={ManaType.GREEN: 2, ManaType.COLORLESS: 3},
        )

        cast_spell_paid(game, p1, spell)
        resolve_top(game)

        assert target.plus_one_counters == 2
        assert game.get_exile(p1).contains(spell)
        assert get_scheduled_paradigm_cards(game, p1) == [spell]
        assert can_cast_paradigm_copy(game, p1, spell) is True

    def test_casting_a_paradigm_copy_keeps_the_source_exiled_and_repeats_the_counter_effect(self) -> None:
        game = create_game()
        p1 = game.players[0]
        game.active_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        initial_creature = Creature(
            name="Initial Creature",
            owner=p1,
            controller=p1,
            base_power=2,
            base_toughness=2,
        )
        later_creature = Creature(
            name="Later Creature",
            owner=p1,
            controller=p1,
            base_power=1,
            base_toughness=1,
        )
        spell = GerminationPracticum(owner=p1, controller=p1)
        set_board_state(
            game,
            0,
            battlefield=[initial_creature],
            hand=[spell],
            mana={ManaType.GREEN: 2, ManaType.COLORLESS: 3},
        )

        cast_spell_paid(game, p1, spell)
        resolve_top(game)

        game.get_battlefield(p1).add(later_creature)
        stack_obj = cast_paradigm_copy(game, p1, spell)

        assert stack_obj.source is not spell
        assert getattr(stack_obj.source, "paradigm_source", None) is spell

        resolve_top(game)

        assert game.get_exile(p1).contains(spell)
        assert get_scheduled_paradigm_cards(game, p1) == [spell]
        assert initial_creature.plus_one_counters == 4
        assert later_creature.plus_one_counters == 2
