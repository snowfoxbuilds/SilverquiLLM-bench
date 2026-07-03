"""Tests for SOS 66 — Run Behind."""

from __future__ import annotations

import pytest

from benchmarks.sos.workspace.cards.sos.sos_66.card_impl import RunBehind
from benchmarks.sos.workspace.engine.casting import CastingError, cast_spell as cast_spell_paid
from benchmarks.sos.workspace.engine.card import CardImpl, Creature, Instant
from benchmarks.sos.workspace.engine.types import ManaCost, ManaType, TargetRequirement, Zone
from benchmarks.sos.workspace.tests.test_utils import create_game, set_board_state


class TestRunBehindProperties:
    """Static card data should match the SOS 66 spec."""

    def test_is_instant(self) -> None:
        assert isinstance(RunBehind(owner=None), Instant)

    def test_name_and_mana_cost(self) -> None:
        card = RunBehind(owner=None)
        assert card.name == "Run Behind"
        assert card.mana_cost == ManaCost.parse("{3}{U}")


class TestRunBehindTargeting:
    """Run Behind should target a creature on the battlefield."""

    def test_returns_single_battlefield_target_requirement(self) -> None:
        game = create_game()
        reqs = RunBehind(owner=None).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.BATTLEFIELD

    def test_target_filter_accepts_creatures_and_rejects_noncreatures(self) -> None:
        game = create_game()
        req = RunBehind(owner=None).get_targets(game)[0]
        creature = Creature(name="Lecture Drake", base_power=2, base_toughness=2)
        noncreature = CardImpl(name="Term Notes")

        assert req.filter_fn(creature) is True
        assert req.filter_fn(noncreature) is False


class TestRunBehindCastingAndResolution:
    """Run Behind should discount itself for attacking targets and tuck them into libraries."""

    def test_targeting_an_attacking_creature_reduces_the_cost_by_one(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target = Creature(
            name="Charging Owl",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        target.is_attacking = True
        spell = RunBehind(owner=p1, controller=p1)

        set_board_state(game, 1, battlefield=[target])
        set_board_state(
            game,
            0,
            hand=[spell],
            mana={ManaType.BLUE: 1, ManaType.COLORLESS: 2},
        )
        p1._script.append(target)

        cast_spell_paid(game, p1, spell)

        assert game.stack.peek().source is spell
        assert p1.mana_pool.total() == 0

    def test_targeting_a_non_attacking_creature_does_not_reduce_the_cost(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target = Creature(
            name="Stationary Owl",
            owner=p2,
            controller=p2,
            base_power=2,
            base_toughness=2,
        )
        spell = RunBehind(owner=p1, controller=p1)

        set_board_state(game, 1, battlefield=[target])
        set_board_state(
            game,
            0,
            hand=[spell],
            mana={ManaType.BLUE: 1, ManaType.COLORLESS: 2},
        )
        p1._script.append(target)

        with pytest.raises(CastingError, match="insufficient mana"):
            cast_spell_paid(game, p1, spell)

        assert game.get_hand(p1).contains(spell)
        assert game.get_battlefield(p2).contains(target)

    def test_on_resolve_puts_the_target_on_top_of_its_owners_library_when_chosen(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target = Creature(
            name="Sky-School Adept",
            owner=p2,
            controller=p2,
            base_power=3,
            base_toughness=2,
        )
        existing = CardImpl(name="Earlier Lesson", owner=p2, controller=p2)
        game.get_library(p2).add(existing)
        set_board_state(game, 1, battlefield=[target])
        p2._script.append(True)

        spell = RunBehind(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.on_resolve(game)

        assert not game.get_battlefield(p2).contains(target)
        assert game.get_library(p2).get_all()[-1] is target

    def test_on_resolve_uses_the_targets_owner_for_the_choice_and_library_destination(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target = Creature(
            name="Borrowed Bird",
            owner=p2,
            controller=p1,
            base_power=2,
            base_toughness=1,
        )
        existing = CardImpl(name="Earlier Lesson", owner=p2, controller=p2)
        game.get_library(p2).add(existing)
        game.get_battlefield(p1).add(target)
        p2._script.append(False)

        spell = RunBehind(owner=p1, controller=p1)
        spell.chosen_targets = [target]
        spell.on_resolve(game)

        assert not game.get_battlefield(p1).contains(target)
        assert not game.get_library(p1).contains(target)
        assert game.get_library(p2).get_all()[0] is target

    def test_no_target_is_a_noop(self) -> None:
        game = create_game()
        p1 = game.players[0]
        spell = RunBehind(owner=p1, controller=p1)

        spell.on_resolve(game)

        assert game.get_library(p1).get_all() == []
        assert game.get_graveyard(p1).get_all() == []
