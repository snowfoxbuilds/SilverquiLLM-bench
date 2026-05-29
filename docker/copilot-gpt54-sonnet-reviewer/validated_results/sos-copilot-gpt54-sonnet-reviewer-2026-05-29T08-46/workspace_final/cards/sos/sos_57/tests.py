"""Tests for SOS 57 — Mana Sculpt."""

from __future__ import annotations

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.casting import cast_spell as engine_cast_spell
from engine.card import Creature, Instant
from engine.stack import StackObject
from engine.types import (
    ManaCost,
    ManaType,
    Phase,
    Step,
    TargetRequirement,
    Zone,
)
from test_utils import create_game, set_board_state


class PaidTestSpell(Instant):
    """Simple instant used as a counterable spell with a total payment of three mana."""

    def __init__(self) -> None:
        super().__init__(name="Paid Test Spell", mana_cost=ManaCost.parse("{2}{R}"))
        self.was_resolved = False

    def on_resolve(self, game) -> None:
        self.was_resolved = True


class DiscountedTestSpell(PaidTestSpell):
    """Spell whose actual mana payment is smaller than its printed mana cost."""

    def __init__(self) -> None:
        super().__init__()
        self.name = "Discounted Test Spell"

    def cost_reduction(self, game) -> int:
        return 2


def _wizard(owner) -> Creature:
    return Creature(
        name="Campus Wizard",
        owner=owner,
        controller=owner,
        subtypes={"Wizard"},
        base_power=1,
        base_toughness=1,
    )


def _resolve_top_of_stack(game) -> None:
    stack_obj = game.stack.pop()
    stack_obj.on_resolve(game)


def _advance_to(
    game,
    *,
    active_player_index: int,
    phase: Phase,
    step: Step | None,
) -> None:
    for _ in range(20):
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


def _setup_counterspell_scenario(
    *,
    target_spell: Instant,
    target_mana: dict[ManaType, int],
    wizard: bool,
    phase: Phase,
    step: Step | None,
):
    game = create_game()
    p1, p2 = game.players
    mana_sculpt = ManaSculpt(owner=p1, controller=p1)

    battlefield = [_wizard(p1)] if wizard else []
    set_board_state(
        game,
        0,
        battlefield=battlefield,
        hand=[mana_sculpt],
        mana={ManaType.BLUE: 2, ManaType.COLORLESS: 1},
    )
    set_board_state(game, 1, hand=[target_spell], mana=target_mana)

    game.active_player_index = 0
    game.priority_player_index = 0
    game.phase = phase
    game.step = step

    engine_cast_spell(game, p2, target_spell)
    target_stack_obj = game.stack.peek()
    assert target_stack_obj is not None

    p1.choose_target = lambda options, requirement: target_stack_obj
    engine_cast_spell(game, p1, mana_sculpt)

    return game, p1, p2, mana_sculpt


class TestManaSculptProperties:
    """Static card data should match the SOS 57 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(ManaSculpt(owner=None), Instant)

    def test_name_and_mana_cost(self) -> None:
        card = ManaSculpt(owner=None)
        assert card.name == "Mana Sculpt"
        assert card.mana_cost == ManaCost.parse("{1}{U}{U}")


class TestManaSculptTargeting:
    """Mana Sculpt targets only spells currently on the stack."""

    def test_cannot_cast_without_a_spell_on_the_stack(self) -> None:
        game = create_game()
        p1 = game.players[0]

        assert ManaSculpt(owner=p1, controller=p1).can_cast(game) is False

    def test_cannot_cast_when_only_a_nonspell_ability_is_on_the_stack(self) -> None:
        game = create_game()
        p1, p2 = game.players
        mana_sculpt = ManaSculpt(owner=p1, controller=p1)

        game.stack.push(StackObject(source=object(), controller=p2, is_spell=False))

        assert mana_sculpt.can_cast(game) is False
        assert mana_sculpt.get_targets(game) == []

    def test_get_targets_returns_a_single_stack_spell_requirement(self) -> None:
        game = create_game()
        p1, p2 = game.players
        mana_sculpt = ManaSculpt(owner=p1, controller=p1)

        spell_obj = StackObject(
            source=PaidTestSpell(),
            controller=p2,
            is_spell=True,
        )
        ability_obj = StackObject(source=object(), controller=p2, is_spell=False)
        game.stack.push(spell_obj)

        requirements = mana_sculpt.get_targets(game)

        assert len(requirements) == 1
        assert isinstance(requirements[0], TargetRequirement)
        assert requirements[0].zone == Zone.STACK
        assert requirements[0].filter_fn(spell_obj) is True
        assert requirements[0].filter_fn(ability_obj) is False


class TestManaSculptResolution:
    """Resolution should counter the target and conditionally create delayed mana."""

    def test_resolution_without_a_target_is_a_noop(self) -> None:
        game = create_game()
        p1 = game.players[0]
        mana_sculpt = ManaSculpt(owner=p1, controller=p1)

        mana_sculpt.on_resolve(game)

        assert game.stack.is_empty()
        assert p1.mana_pool.total() == 0

    def test_counters_target_spell_and_moves_it_to_its_owners_graveyard(self) -> None:
        target_spell = PaidTestSpell()
        game, p1, p2, mana_sculpt = _setup_counterspell_scenario(
            target_spell=target_spell,
            target_mana={ManaType.RED: 1, ManaType.COLORLESS: 2},
            wizard=False,
            phase=Phase.PRECOMBAT_MAIN,
            step=None,
        )

        _resolve_top_of_stack(game)

        assert target_spell.was_resolved is False
        assert game.get_graveyard(p2).contains(target_spell)
        assert not p2.zones[Zone.STACK].contains(target_spell)
        assert game.get_graveyard(p1).contains(mana_sculpt)
        assert game.stack.is_empty()

    def test_without_a_wizard_no_delayed_colorless_is_added_at_next_main_phase(self) -> None:
        target_spell = PaidTestSpell()
        game, p1, _p2, _mana_sculpt = _setup_counterspell_scenario(
            target_spell=target_spell,
            target_mana={ManaType.RED: 1, ManaType.COLORLESS: 2},
            wizard=False,
            phase=Phase.COMBAT,
            step=Step.END_COMBAT,
        )

        _resolve_top_of_stack(game)
        assert p1.mana_pool.total() == 0

        game.advance_phase()

        assert game.phase == Phase.POSTCOMBAT_MAIN
        assert game.step is None
        assert p1.mana_pool.total() == 0

    def test_with_a_wizard_adds_colorless_equal_to_total_mana_spent_at_your_next_main_phase(self) -> None:
        target_spell = PaidTestSpell()
        game, p1, _p2, _mana_sculpt = _setup_counterspell_scenario(
            target_spell=target_spell,
            target_mana={ManaType.RED: 1, ManaType.COLORLESS: 2},
            wizard=True,
            phase=Phase.COMBAT,
            step=Step.END_COMBAT,
        )

        _resolve_top_of_stack(game)
        assert p1.mana_pool.total() == 0

        game.advance_phase()

        assert game.phase == Phase.POSTCOMBAT_MAIN
        assert game.step is None
        assert p1.mana_pool.get(ManaType.COLORLESS) == 3
        assert p1.mana_pool.total() == 3

    def test_delayed_colorless_uses_actual_mana_spent_not_printed_mana_cost(self) -> None:
        target_spell = DiscountedTestSpell()
        game, p1, _p2, _mana_sculpt = _setup_counterspell_scenario(
            target_spell=target_spell,
            target_mana={ManaType.RED: 1},
            wizard=True,
            phase=Phase.COMBAT,
            step=Step.END_COMBAT,
        )

        _resolve_top_of_stack(game)
        game.advance_phase()

        assert game.phase == Phase.POSTCOMBAT_MAIN
        assert game.step is None
        assert p1.mana_pool.get(ManaType.COLORLESS) == 1
        assert p1.mana_pool.total() == 1

    def test_if_cast_in_postcombat_main_it_waits_for_your_next_turns_main_phase(self) -> None:
        target_spell = PaidTestSpell()
        game, p1, _p2, _mana_sculpt = _setup_counterspell_scenario(
            target_spell=target_spell,
            target_mana={ManaType.RED: 1, ManaType.COLORLESS: 2},
            wizard=True,
            phase=Phase.POSTCOMBAT_MAIN,
            step=None,
        )

        _resolve_top_of_stack(game)
        assert p1.mana_pool.total() == 0

        _advance_to(
            game,
            active_player_index=1,
            phase=Phase.PRECOMBAT_MAIN,
            step=None,
        )
        assert p1.mana_pool.total() == 0

        _advance_to(
            game,
            active_player_index=1,
            phase=Phase.POSTCOMBAT_MAIN,
            step=None,
        )
        assert p1.mana_pool.total() == 0

        _advance_to(
            game,
            active_player_index=0,
            phase=Phase.PRECOMBAT_MAIN,
            step=None,
        )
        assert p1.mana_pool.get(ManaType.COLORLESS) == 3
        assert p1.mana_pool.total() == 3
