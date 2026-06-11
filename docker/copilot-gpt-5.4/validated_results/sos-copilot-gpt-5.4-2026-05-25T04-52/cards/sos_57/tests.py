"""Tests for SOS 57 — Mana Sculpt."""

from __future__ import annotations

from benchmarks.sos.workspace.cards.sos.sos_57.card_impl import ManaSculpt
from benchmarks.sos.workspace.engine.casting import cast_spell as cast_spell_paid, resolve_top
from benchmarks.sos.workspace.engine.card import Creature, Instant
from benchmarks.sos.workspace.engine.events import (
    BeginningOfFirstMainPhaseTriggeredEvent,
    BeginningOfMainPhaseTriggeredEvent,
)
from benchmarks.sos.workspace.engine.stack import StackObject
from benchmarks.sos.workspace.engine.types import ManaCost, ManaType, Phase, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


def _put_spell_on_stack(game: object, player: object, spell: object) -> StackObject:
    player.zones[Zone.STACK].add(spell)
    stack_obj = StackObject(source=spell, controller=player)
    game.stack.push(stack_obj)
    return stack_obj


class TestManaSculptProperties:
    """Static card data should match the SOS 57 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(ManaSculpt(owner=None), Instant)

    def test_name_and_mana_cost(self) -> None:
        card = ManaSculpt(owner=None)
        assert card.name == "Mana Sculpt"
        assert card.mana_cost == ManaCost.parse("{1}{U}{U}")


class TestManaSculptTargeting:
    """Mana Sculpt should target a spell on the stack."""

    def test_returns_single_stack_target_requirement(self) -> None:
        game = create_game()
        reqs = ManaSculpt(owner=None).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.STACK

    def test_target_filter_accepts_spell_stack_objects_and_rejects_nonspell_stack_objects(self) -> None:
        game = create_game()
        req = ManaSculpt(owner=None).get_targets(game)[0]
        spell_obj = StackObject(
            source=Instant(name="Study Notes", mana_cost=ManaCost.parse("{U}")),
            controller=game.players[0],
            is_spell=True,
        )
        ability_obj = StackObject(
            source=object(),
            controller=game.players[0],
            is_spell=False,
        )

        assert req.filter_fn(spell_obj) is True
        assert req.filter_fn(ability_obj) is False


class TestManaSculptResolution:
    """Mana Sculpt should counter a spell and optionally defer colorless mana."""

    def test_on_resolution_it_counters_the_target_spell_and_puts_it_into_its_owners_graveyard(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target_spell = Instant(
            name="Lecture Note",
            owner=p2,
            controller=p2,
            mana_cost=ManaCost.parse("{2}{U}"),
        )
        target_stack_obj = _put_spell_on_stack(game, p2, target_spell)
        spell = ManaSculpt(owner=p1, controller=p1)

        set_board_state(game, 0, hand=[spell], mana={ManaType.BLUE: 2, ManaType.COLORLESS: 1})
        p1._script.append(target_stack_obj)

        cast_spell_paid(game, p1, spell)
        resolve_top(game)

        assert not game.stack.contains(target_stack_obj)
        assert not p2.zones[Zone.STACK].contains(target_spell)
        assert game.get_graveyard(p2).contains(target_spell)
        assert game.get_graveyard(p1).contains(spell)

    def test_controlling_a_wizard_delays_colorless_mana_equal_to_the_countered_spells_mana_spent(self) -> None:
        game = create_game()
        p1, p2 = game.players
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None

        wizard = Creature(
            name="Apprentice Wizard",
            owner=p1,
            controller=p1,
            subtypes={"Human", "Wizard"},
            base_power=1,
            base_toughness=1,
        )
        target_spell = Instant(
            name="Big Lesson",
            owner=p2,
            controller=p2,
            mana_cost=ManaCost.parse("{2}{U}"),
        )
        target_spell.mana_spent = 4  # type: ignore[attr-defined]
        target_stack_obj = _put_spell_on_stack(game, p2, target_spell)
        spell = ManaSculpt(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[wizard],
            hand=[spell],
            mana={ManaType.BLUE: 2, ManaType.COLORLESS: 1},
        )
        p1._script.append(target_stack_obj)

        cast_spell_paid(game, p1, spell)
        resolve_top(game)

        assert p1.mana_pool.total() == 0

        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        game.trigger_manager.fire_event(game, BeginningOfFirstMainPhaseTriggeredEvent(player=p1))

        assert len(game.stack) == 1

        resolve_top(game)

        assert p1.mana_pool.get(ManaType.COLORLESS) == 4

    def test_with_a_wizard_it_grants_colorless_mana_at_the_same_turns_postcombat_main(self) -> None:
        game = create_game()
        p1, p2 = game.players
        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None

        wizard = Creature(
            name="Apprentice Wizard",
            owner=p1,
            controller=p1,
            subtypes={"Human", "Wizard"},
            base_power=1,
            base_toughness=1,
        )
        target_spell = Instant(
            name="Big Lesson",
            owner=p2,
            controller=p2,
            mana_cost=ManaCost.parse("{2}{U}"),
        )
        target_spell.mana_spent = 4  # type: ignore[attr-defined]
        target_stack_obj = _put_spell_on_stack(game, p2, target_spell)
        spell = ManaSculpt(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[wizard],
            hand=[spell],
            mana={ManaType.BLUE: 2, ManaType.COLORLESS: 1},
        )
        p1._script.append(target_stack_obj)

        cast_spell_paid(game, p1, spell)
        resolve_top(game)

        assert p1.mana_pool.total() == 0

        game.phase = Phase.POSTCOMBAT_MAIN
        game.step = None
        game.trigger_manager.fire_event(
            game,
            BeginningOfMainPhaseTriggeredEvent(player=p1, phase=Phase.POSTCOMBAT_MAIN),
        )

        assert len(game.stack) == 1

        resolve_top(game)

        assert p1.mana_pool.get(ManaType.COLORLESS) == 4

        game.turn_number += 1
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        game.trigger_manager.fire_event(game, BeginningOfFirstMainPhaseTriggeredEvent(player=p1))

        assert game.stack.is_empty()
        assert p1.mana_pool.get(ManaType.COLORLESS) == 4

    def test_without_a_wizard_it_does_not_grant_delayed_colorless_mana(self) -> None:
        game = create_game()
        p1, p2 = game.players
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None

        target_spell = Instant(
            name="Big Lesson",
            owner=p2,
            controller=p2,
            mana_cost=ManaCost.parse("{2}{U}"),
        )
        target_spell.mana_spent = 4  # type: ignore[attr-defined]
        target_stack_obj = _put_spell_on_stack(game, p2, target_spell)
        spell = ManaSculpt(owner=p1, controller=p1)

        set_board_state(game, 0, hand=[spell], mana={ManaType.BLUE: 2, ManaType.COLORLESS: 1})
        p1._script.append(target_stack_obj)

        cast_spell_paid(game, p1, spell)
        resolve_top(game)

        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        game.trigger_manager.fire_event(game, BeginningOfFirstMainPhaseTriggeredEvent(player=p1))

        assert game.stack.is_empty()
        assert p1.mana_pool.get(ManaType.COLORLESS) == 0
