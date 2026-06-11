"""Tests for SOS 39 — Brush Off."""

from __future__ import annotations

import pytest

from benchmarks.sos.workspace.cards.sos.sos_39.card_impl import BrushOff
from benchmarks.sos.workspace.engine.casting import CastingError, cast_spell as cast_spell_paid, resolve_top
from benchmarks.sos.workspace.engine.card import Creature, Instant
from benchmarks.sos.workspace.engine.stack import StackObject
from benchmarks.sos.workspace.engine.types import ManaCost, ManaType, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


def _put_spell_on_stack(game: object, player: object, spell: object) -> StackObject:
    player.zones[Zone.STACK].add(spell)
    stack_obj = StackObject(source=spell, controller=player)
    game.stack.push(stack_obj)
    return stack_obj


class TestBrushOffProperties:
    """Static card data should match the SOS 39 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(BrushOff(owner=None), Instant)

    def test_name_and_mana_cost(self) -> None:
        card = BrushOff(owner=None)
        assert card.name == "Brush Off"
        assert card.mana_cost == ManaCost.parse("{2}{U}{U}")


class TestBrushOffTargeting:
    """Brush Off should target a spell on the stack."""

    def test_returns_single_stack_target_requirement(self) -> None:
        game = create_game()
        reqs = BrushOff(owner=None).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.STACK

    def test_target_filter_accepts_spells_on_the_stack_and_rejects_nonstack_objects(self) -> None:
        game = create_game()
        req = BrushOff(owner=None).get_targets(game)[0]
        spell_obj = StackObject(
            source=Instant(name="Study Notes", mana_cost=ManaCost.parse("{U}")),
            controller=game.players[0],
        )
        non_spell = Creature(name="Target Bear", base_power=2, base_toughness=2)

        assert req.filter_fn(spell_obj) is True
        assert req.filter_fn(non_spell) is False


class TestBrushOffCastingAndResolution:
    """Brush Off should discount itself against instants or sorceries and counter its target."""

    def test_targeting_an_instant_or_sorcery_spell_reduces_the_cost_to_one_and_blue(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target_spell = Instant(
            name="Study Notes",
            owner=p2,
            controller=p2,
            mana_cost=ManaCost.parse("{U}"),
        )
        target_stack_obj = _put_spell_on_stack(game, p2, target_spell)
        spell = BrushOff(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            hand=[spell],
            mana={ManaType.BLUE: 1, ManaType.COLORLESS: 1},
        )
        p1._script.append(target_stack_obj)

        cast_spell_paid(game, p1, spell)

        assert game.stack.peek().source is spell
        assert p1.mana_pool.total() == 0

    def test_targeting_a_noninstant_nonsorcery_spell_does_not_reduce_the_cost(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target_spell = Creature(
            name="Campus Guard",
            owner=p2,
            controller=p2,
            mana_cost=ManaCost.parse("{2}"),
            base_power=2,
            base_toughness=2,
        )
        target_stack_obj = _put_spell_on_stack(game, p2, target_spell)
        spell = BrushOff(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            hand=[spell],
            mana={ManaType.BLUE: 1, ManaType.COLORLESS: 1},
        )
        p1._script.append(target_stack_obj)

        with pytest.raises(CastingError, match="insufficient mana"):
            cast_spell_paid(game, p1, spell)

        assert game.get_hand(p1).contains(spell)
        assert game.stack.contains(target_stack_obj)

    def test_on_resolution_it_counters_the_target_spell_and_puts_it_into_its_owners_graveyard(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target_spell = Instant(
            name="Study Notes",
            owner=p2,
            controller=p2,
            mana_cost=ManaCost.parse("{U}"),
        )
        target_stack_obj = _put_spell_on_stack(game, p2, target_spell)
        spell = BrushOff(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            hand=[spell],
            mana={ManaType.BLUE: 1, ManaType.COLORLESS: 1},
        )
        p1._script.append(target_stack_obj)

        cast_spell_paid(game, p1, spell)
        resolve_top(game)

        assert not game.stack.contains(target_stack_obj)
        assert not p2.zones[Zone.STACK].contains(target_spell)
        assert game.get_graveyard(p2).contains(target_spell)
        assert game.get_graveyard(p1).contains(spell)
