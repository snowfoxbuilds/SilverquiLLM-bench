"""Tests for SOS 57 — Mana Sculpt."""

from __future__ import annotations

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.casting import cast_spell as cast_spell_to_stack
from engine.card import Creature, Instant
from engine.stack import StackObject
from engine.state_based_actions import resolve_state_based_actions
from engine.types import CardType, ManaCost, ManaType, Phase, TargetRequirement, Zone
from test_utils import advance_to_phase, create_game, set_board_state


def _resolve_all(game) -> None:
    while not game.stack.is_empty():
        obj = game.stack.pop()
        obj.on_resolve(game)
        resolve_state_based_actions(game)


def _wizard(owner) -> Creature:
    wizard = Creature(
        name="Test Wizard",
        owner=owner,
        controller=owner,
        base_power=1,
        base_toughness=1,
    )
    wizard.card_types = {CardType.CREATURE}
    wizard.subtypes = {"Human", "Wizard"}
    return wizard


def _target_spell(owner) -> Creature:
    spell = Creature(
        name="Costly Bear",
        owner=owner,
        controller=owner,
        mana_cost=ManaCost.parse("{3}"),
        base_power=3,
        base_toughness=3,
    )
    spell.card_types = {CardType.CREATURE}
    return spell


class _ReducedCostTargetSpell(Creature):
    def cost_reduction(self, game) -> int:
        return 2


def _reduced_cost_target_spell(owner) -> Creature:
    spell = _ReducedCostTargetSpell(
        name="Discount Colossus",
        owner=owner,
        controller=owner,
        mana_cost=ManaCost.parse("{5}"),
        base_power=5,
        base_toughness=5,
    )
    spell.card_types = {CardType.CREATURE}
    return spell


def _set_precombat_main(game) -> None:
    game.active_player_index = 0
    game.priority_player_index = 0
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None


class TestManaSculptProperties:
    def test_is_instant(self) -> None:
        assert isinstance(ManaSculpt(owner=None), Instant)

    def test_name(self) -> None:
        assert ManaSculpt(owner=None).name == "Mana Sculpt"

    def test_mana_cost(self) -> None:
        assert ManaSculpt(owner=None).mana_cost == ManaCost.parse("{1}{U}{U}")


class TestManaSculptTargeting:
    def test_cannot_be_cast_without_a_spell_on_the_stack(self) -> None:
        game = create_game()
        p1 = game.players[0]

        assert ManaSculpt(owner=p1, controller=p1).can_cast(game) is False

    def test_targets_a_spell_on_the_stack(self) -> None:
        game = create_game()
        p1 = game.players[0]
        target_spell = _target_spell(p1)

        set_board_state(
            game,
            0,
            hand=[target_spell],
            mana={ManaType.COLORLESS: 3},
        )
        _set_precombat_main(game)
        cast_spell_to_stack(game, p1, target_spell)

        reqs = ManaSculpt(owner=p1, controller=p1).get_targets(game)

        assert len(reqs) == 1
        req = reqs[0]
        assert isinstance(req, TargetRequirement)
        assert req.zone is Zone.STACK

        spell_on_stack = game.stack.peek()
        assert spell_on_stack is not None
        assert req.filter_fn(spell_on_stack) is True

        non_spell = StackObject(source=None, controller=p1)
        non_spell.is_spell = False
        assert req.filter_fn(non_spell) is False
        assert req.filter_fn(Creature(name="Ground Bear", base_power=2, base_toughness=2)) is False


class TestManaSculptResolution:
    def test_counters_target_spell_and_adds_no_mana_without_a_wizard(self) -> None:
        game = create_game()
        p1 = game.players[0]
        target_spell = _target_spell(p1)
        mana_sculpt = ManaSculpt(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            hand=[target_spell, mana_sculpt],
            mana={ManaType.COLORLESS: 4, ManaType.BLUE: 2},
        )
        _set_precombat_main(game)

        cast_spell_to_stack(game, p1, target_spell)
        target_on_stack = game.stack.peek()
        assert target_on_stack is not None
        p1._script.append(target_on_stack)

        cast_spell_to_stack(game, p1, mana_sculpt)
        _resolve_all(game)

        assert game.get_graveyard(p1).contains(target_spell)
        assert not game.get_battlefield(p1).contains(target_spell)
        assert p1.mana_pool.total() == 0

        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)
        _resolve_all(game)

        assert p1.mana_pool.get(ManaType.COLORLESS) == 0

    def test_with_a_wizard_it_adds_colorless_at_your_next_main_phase_equal_to_mana_spent(self) -> None:
        game = create_game()
        p1 = game.players[0]
        wizard = _wizard(p1)
        target_spell = _target_spell(p1)
        mana_sculpt = ManaSculpt(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[wizard],
            hand=[target_spell, mana_sculpt],
            mana={ManaType.COLORLESS: 4, ManaType.BLUE: 2},
        )
        _set_precombat_main(game)

        cast_spell_to_stack(game, p1, target_spell)
        target_on_stack = game.stack.peek()
        assert target_on_stack is not None
        p1._script.append(target_on_stack)

        cast_spell_to_stack(game, p1, mana_sculpt)
        _resolve_all(game)

        assert game.get_graveyard(p1).contains(target_spell)
        assert p1.mana_pool.total() == 0

        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)
        _resolve_all(game)

        assert p1.mana_pool.get(ManaType.COLORLESS) == 3

    def test_with_a_wizard_it_uses_actual_mana_spent_not_printed_cost_for_a_reduced_cost_spell(self) -> None:
        game = create_game()
        p1 = game.players[0]
        wizard = _wizard(p1)
        target_spell = _reduced_cost_target_spell(p1)
        mana_sculpt = ManaSculpt(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            battlefield=[wizard],
            hand=[target_spell, mana_sculpt],
            mana={ManaType.COLORLESS: 4, ManaType.BLUE: 2},
        )
        _set_precombat_main(game)

        cast_spell_to_stack(game, p1, target_spell)
        target_on_stack = game.stack.peek()
        assert target_on_stack is not None
        assert target_spell.total_mana_spent == 3
        assert target_on_stack.total_mana_spent == 3
        p1._script.append(target_on_stack)

        cast_spell_to_stack(game, p1, mana_sculpt)
        _resolve_all(game)

        assert game.get_graveyard(p1).contains(target_spell)
        assert p1.mana_pool.total() == 0

        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)
        _resolve_all(game)

        assert p1.mana_pool.get(ManaType.COLORLESS) == 3
