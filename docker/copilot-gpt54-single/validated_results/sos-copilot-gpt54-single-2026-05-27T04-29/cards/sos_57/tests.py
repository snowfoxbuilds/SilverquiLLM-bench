"""Tests for SOS 57 — Mana Sculpt."""

from __future__ import annotations

import pytest

from cards.sos.sos_57.card_impl import ManaSculpt
from engine.card import Creature, Instant, Sorcery
from engine.casting import (
    CastingError,
    cast_spell as cast_without_resolution,
    resolve_top,
)
from engine.stack import StackObject
from engine.types import CardType, ManaCost, ManaType, Phase, Step, TargetRequirement, Zone
from test_utils import advance_to_phase, create_game, set_board_state


class TestManaSculptProperties:
    """Static characteristics from the card spec."""

    def test_is_an_instant_named_mana_sculpt(self) -> None:
        card = ManaSculpt(owner=None)
        assert isinstance(card, Instant)
        assert CardType.INSTANT in card.card_types
        assert card.name == "Mana Sculpt"

    def test_mana_cost_matches_the_spec(self) -> None:
        assert ManaSculpt(owner=None).mana_cost == ManaCost.parse("{1}{U}{U}")


class TestManaSculptTargeting:
    """Mana Sculpt can only be cast for and target a spell on the stack."""

    def test_cannot_be_cast_when_no_spell_is_on_the_stack(self) -> None:
        game = create_game()
        player = game.players[0]
        sculpt = ManaSculpt(owner=player, controller=player)

        set_board_state(
            game,
            0,
            hand=[sculpt],
            mana={ManaType.BLUE: 2, ManaType.COLORLESS: 1},
        )
        game.active_player_index = 0
        game.priority_player_index = 0
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None

        with pytest.raises(CastingError):
            cast_without_resolution(game, player, sculpt)

    def test_get_targets_returns_one_stack_spell_requirement(self) -> None:
        game = create_game()
        p2 = game.players[1]
        target_spell = Sorcery(
            name="Volcanic Lesson",
            mana_cost=ManaCost.parse("{1}{R}"),
            owner=p2,
            controller=p2,
        )

        set_board_state(game, 1, hand=[target_spell], mana={ManaType.RED: 2})
        game.active_player_index = 1
        game.priority_player_index = 1
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        cast_without_resolution(game, p2, target_spell)

        reqs = ManaSculpt(owner=game.players[0], controller=game.players[0]).get_targets(game)

        assert isinstance(reqs, list)
        assert len(reqs) == 1
        assert isinstance(reqs[0], TargetRequirement)
        assert reqs[0].zone == Zone.STACK
        assert reqs[0].filter_fn(game.stack.peek()) is True

        non_spell_obj = StackObject(source=None, controller=p2)
        non_spell_obj.is_spell = False
        assert reqs[0].filter_fn(non_spell_obj) is False


class TestManaSculptResolution:
    """Resolution contract for the counterspell half of Mana Sculpt."""

    @staticmethod
    def _cast_target_spell(game):
        p2 = game.players[1]
        target_spell = Sorcery(
            name="Volcanic Lesson",
            mana_cost=ManaCost.parse("{1}{R}"),
        )
        set_board_state(game, 1, hand=[target_spell], mana={ManaType.RED: 2})
        game.active_player_index = 1
        game.priority_player_index = 1
        game.phase = Phase.PRECOMBAT_MAIN
        game.step = None
        cast_without_resolution(game, p2, target_spell)
        return target_spell, game.stack.peek()

    def test_counters_the_target_spell_and_puts_it_into_its_owners_graveyard(self) -> None:
        game = create_game()
        p1, p2 = game.players
        target_spell, target_stack_obj = self._cast_target_spell(game)
        sculpt = ManaSculpt(owner=p1, controller=p1)

        set_board_state(
            game,
            0,
            hand=[sculpt],
            mana={ManaType.BLUE: 2, ManaType.COLORLESS: 1},
        )
        p1.choose_target = lambda _options, _requirement: target_stack_obj

        cast_without_resolution(game, p1, sculpt)
        sculpt_stack_obj = game.stack.pop()
        sculpt_stack_obj.on_resolve(game)

        assert game.get_graveyard(p2).contains(target_spell)
        assert not p2.zones[Zone.STACK].contains(target_spell)
        assert game.get_graveyard(p1).contains(sculpt)
        assert game.stack.is_empty()


class TestManaSculptDelayedMana:
    """Delayed mana payout tracks the countered spell and the next main phase."""

    @staticmethod
    def _wizard(owner):
        return Creature(
            name="Apprentice Channeler",
            owner=owner,
            controller=owner,
            subtypes={"Wizard"},
            base_power=1,
            base_toughness=1,
        )

    @staticmethod
    def _resolve_with_optional_wizard(game, *, with_wizard: bool):
        p1, p2 = game.players
        target_spell = Instant(
            name="Volcanic Insight",
            mana_cost=ManaCost.parse("{1}{R}"),
            owner=p2,
            controller=p2,
        )
        set_board_state(game, 1, hand=[target_spell], mana={ManaType.RED: 2})
        game.active_player_index = 0
        game.priority_player_index = 1
        game.phase = Phase.COMBAT
        game.step = Step.BEGIN_COMBAT
        cast_without_resolution(game, p2, target_spell)
        target_stack_obj = game.stack.peek()
        sculpt = ManaSculpt(owner=p1, controller=p1)
        battlefield = [TestManaSculptDelayedMana._wizard(p1)] if with_wizard else []

        set_board_state(
            game,
            0,
            battlefield=battlefield,
            hand=[sculpt],
            mana={ManaType.BLUE: 2, ManaType.COLORLESS: 1},
        )
        p1.choose_target = lambda _options, _requirement: target_stack_obj

        cast_without_resolution(game, p1, sculpt)
        game.stack.pop().on_resolve(game)
        return sculpt, target_spell

    def test_wizard_schedules_colorless_for_only_your_next_main_phase(self) -> None:
        game = create_game()
        p1 = game.players[0]
        _sculpt, target_spell = self._resolve_with_optional_wizard(game, with_wizard=True)

        assert p1.mana_pool.total() == 0

        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)
        resolve_top(game)
        assert p1.mana_pool.get(ManaType.COLORLESS) == target_spell.mana_spent_to_cast
        assert p1.mana_pool.total() == target_spell.mana_spent_to_cast

        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        resolve_top(game)
        assert p1.mana_pool.total() == 0

        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)
        resolve_top(game)
        assert p1.mana_pool.total() == 0

        advance_to_phase(game, Phase.PRECOMBAT_MAIN)
        resolve_top(game)
        assert p1.mana_pool.total() == 0

    def test_no_wizard_means_no_delayed_mana_is_created(self) -> None:
        game = create_game()
        p1 = game.players[0]
        _sculpt, _target_spell = self._resolve_with_optional_wizard(game, with_wizard=False)

        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)
        resolve_top(game)

        assert p1.mana_pool.total() == 0
        assert game.stack.is_empty()

    def test_delayed_mana_still_arrives_if_the_wizard_leaves_before_that_main_phase(self) -> None:
        game = create_game()
        p1 = game.players[0]
        _sculpt, target_spell = self._resolve_with_optional_wizard(game, with_wizard=True)

        set_board_state(game, 0, battlefield=[])

        advance_to_phase(game, Phase.POSTCOMBAT_MAIN)
        resolve_top(game)

        assert p1.mana_pool.get(ManaType.COLORLESS) == target_spell.mana_spent_to_cast
