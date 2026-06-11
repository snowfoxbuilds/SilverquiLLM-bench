"""Tests for SOS 47 — Essence Scatter."""

from __future__ import annotations

import pytest

from benchmarks.sos.workspace.cards.sos.sos_47.card_impl import EssenceScatter
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


class TestEssenceScatterProperties:
    """Static card data should match the SOS 47 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(EssenceScatter(owner=None), Instant)

    def test_name_and_mana_cost(self) -> None:
        card = EssenceScatter(owner=None)
        assert card.name == "Essence Scatter"
        assert card.mana_cost == ManaCost.parse("{1}{U}")


class TestEssenceScatterTargeting:
    """Essence Scatter should target a creature spell on the stack."""

    def test_returns_single_stack_target_requirement(self) -> None:
        game = create_game()
        reqs = EssenceScatter(owner=None).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.STACK

    def test_target_filter_accepts_creature_spells_and_rejects_noncreature_spells(self) -> None:
        game = create_game()
        req = EssenceScatter(owner=None).get_targets(game)[0]
        creature_spell = StackObject(
            source=Creature(
                name="Campus Guard",
                mana_cost=ManaCost.parse("{2}"),
                base_power=2,
                base_toughness=2,
            ),
            controller=game.players[0],
            is_spell=True,
        )
        instant_spell = StackObject(
            source=Instant(name="Study Notes", mana_cost=ManaCost.parse("{U}")),
            controller=game.players[0],
            is_spell=True,
        )

        assert req.filter_fn(creature_spell) is True
        assert req.filter_fn(instant_spell) is False


class TestEssenceScatterCastingAndResolution:
    """Essence Scatter should counter a creature spell."""

    def test_cannot_target_a_noncreature_spell(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target_spell = Instant(
            name="Study Notes",
            owner=p2,
            controller=p2,
            mana_cost=ManaCost.parse("{U}"),
        )
        target_stack_obj = _put_spell_on_stack(game, p2, target_spell)
        spell = EssenceScatter(owner=p1, controller=p1)

        set_board_state(game, 0, hand=[spell], mana={ManaType.BLUE: 2})
        p1._script.append(target_stack_obj)

        with pytest.raises(CastingError, match="chosen target does not satisfy filter"):
            cast_spell_paid(game, p1, spell)

        assert game.get_hand(p1).contains(spell)
        assert game.stack.contains(target_stack_obj)

    def test_on_resolution_it_counters_the_target_creature_spell(self) -> None:
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
        spell = EssenceScatter(owner=p1, controller=p1)

        set_board_state(game, 0, hand=[spell], mana={ManaType.BLUE: 2})
        p1._script.append(target_stack_obj)

        cast_spell_paid(game, p1, spell)
        resolve_top(game)

        assert not game.stack.contains(target_stack_obj)
        assert not p2.zones[Zone.STACK].contains(target_spell)
        assert game.get_graveyard(p2).contains(target_spell)
        assert game.get_graveyard(p1).contains(spell)
