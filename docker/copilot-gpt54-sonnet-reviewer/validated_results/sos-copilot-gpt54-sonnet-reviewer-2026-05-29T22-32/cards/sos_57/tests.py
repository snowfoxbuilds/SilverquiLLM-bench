"""Tests for SOS 57 — Mana Sculpt."""

from __future__ import annotations

from types import MethodType

import pytest

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature, Instant
from engine.casting import CastingError, cast_spell as cast_spell_to_stack
from engine.types import ManaCost, ManaType, Phase, TargetRequirement, Zone
from test_utils import advance_to_phase, create_game, set_board_state


def _bind_choose_target(player, chosen_target) -> None:
    def choose_target(self, options, requirement):
        return chosen_target

    player.choose_target = MethodType(choose_target, player)


def _make_target_spell(name: str = 'Expensive Spell') -> Instant:
    return Instant(name=name, mana_cost=ManaCost.parse('{2}{R}'))


def _make_wizard(name: str = 'Apprentice Wizard') -> Creature:
    return Creature(
        name=name,
        subtypes={'Wizard'},
        base_power=1,
        base_toughness=1,
    )


def _cast_and_resolve_mana_sculpt(*, controller_has_wizard: bool):
    game = create_game()
    game.phase = Phase.PRECOMBAT_MAIN
    game.step = None
    game.active_player_index = 0
    game.priority_player_index = 0

    p1, p2 = game.players
    mana_sculpt = ManaSculpt(owner=p1, controller=p1)
    target_spell = _make_target_spell()

    battlefield = [_make_wizard()] if controller_has_wizard else []
    set_board_state(
        game,
        0,
        battlefield=battlefield,
        hand=[mana_sculpt],
        mana={ManaType.BLUE: 2, ManaType.COLORLESS: 1},
    )
    set_board_state(
        game,
        1,
        hand=[target_spell],
        mana={ManaType.RED: 1, ManaType.COLORLESS: 2},
    )

    cast_spell_to_stack(game, p2, target_spell)
    target_stack_obj = game.stack.peek()
    assert target_stack_obj is not None

    _bind_choose_target(p1, target_stack_obj)
    cast_spell_to_stack(game, p1, mana_sculpt)

    mana_sculpt_stack_obj = game.stack.pop()
    assert mana_sculpt_stack_obj.source is mana_sculpt
    mana_sculpt_stack_obj.on_resolve(game)

    return game, p1, p2, mana_sculpt, target_spell


class TestManaSculptProperties:
    """Static characteristics from the card spec."""

    def test_is_an_instant_named_mana_sculpt(self) -> None:
        card = ManaSculpt(owner=None)
        assert isinstance(card, Instant)
        assert card.name == 'Mana Sculpt'

    def test_mana_cost_is_one_blue_blue(self) -> None:
        assert ManaSculpt(owner=None).mana_cost == ManaCost.parse('{1}{U}{U}')


class TestManaSculptTargeting:
    """Mana Sculpt targets a spell on the stack and requires one to exist."""

    def test_declares_a_single_stack_spell_target_requirement(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target_spell = _make_target_spell()

        set_board_state(game, 1, hand=[target_spell], mana={ManaType.RED: 1, ManaType.COLORLESS: 2})
        cast_spell_to_stack(game, p2, target_spell)
        target_stack_obj = game.stack.peek()
        assert target_stack_obj is not None

        reqs = ManaSculpt(owner=p1).get_targets(game)
        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.STACK
        assert reqs[0].filter_fn(target_stack_obj) is True
        assert reqs[0].filter_fn(Creature(name='Bear', base_power=2, base_toughness=2)) is False

    def test_casting_with_no_spell_on_stack_is_illegal(self) -> None:
        game = create_game()
        p1 = game.players[0]
        card = ManaSculpt(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            hand=[card],
            mana={ManaType.BLUE: 2, ManaType.COLORLESS: 1},
        )

        with pytest.raises(CastingError):
            cast_spell_to_stack(game, p1, card)


class TestManaSculptResolution:
    """Counterspell resolution and delayed mana contract."""

    def test_resolve_counters_the_targeted_spell(self) -> None:
        game, p1, p2, mana_sculpt, target_spell = _cast_and_resolve_mana_sculpt(
            controller_has_wizard=False,
        )

        assert game.stack.is_empty()
        assert game.get_graveyard(p2).contains(target_spell)
        assert game.get_graveyard(p1).contains(mana_sculpt)
        assert not p2.zones[Zone.STACK].contains(target_spell)

    def test_with_a_wizard_you_add_colorless_at_your_next_main_phase_equal_to_mana_spent(self) -> None:
        game, p1, _p2, _mana_sculpt, _target_spell = _cast_and_resolve_mana_sculpt(
            controller_has_wizard=True,
        )

        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)

        assert p1.mana_pool.get(ManaType.COLORLESS) == 3
        assert p1.mana_pool.total() == 3

    def test_without_a_wizard_you_do_not_add_colorless_at_your_next_main_phase(self) -> None:
        game, p1, _p2, _mana_sculpt, _target_spell = _cast_and_resolve_mana_sculpt(
            controller_has_wizard=False,
        )

        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)

        assert p1.mana_pool.total() == 0

    def test_losing_the_wizard_after_resolution_does_not_stop_the_delayed_mana(self) -> None:
        game, p1, _p2, _mana_sculpt, _target_spell = _cast_and_resolve_mana_sculpt(
            controller_has_wizard=True,
        )

        set_board_state(game, 0, battlefield=[])
        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)

        assert p1.mana_pool.get(ManaType.COLORLESS) == 3
